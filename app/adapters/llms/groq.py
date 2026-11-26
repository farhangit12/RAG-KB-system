"""Groq LLM over its OpenAI-compatible HTTP API (free plan, no card on the account).

Free-plan limits are per model and per organisation (requests and tokens per minute and
per day). On HTTP 429 we wait for ``retry-after`` and try again, up to GROQ_MAX_RETRIES,
then raise ``LLMRateLimitedError`` so the caller can queue the request instead of paying.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

import httpx

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class LLMRateLimitedError(RuntimeError):
    """The free-plan limit was hit and retries ran out."""


class GroqLLM:
    """Chat completions via httpx; no SDK needed."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if settings.groq_api_key is None:
            raise ValueError("GROQ_API_KEY is not set (use LLM=fake for offline runs)")
        self._s = settings
        self._client = client or httpx.Client(
            base_url=settings.groq_base_url,
            timeout=settings.groq_timeout_s,
            headers={"Authorization": f"Bearer {settings.groq_api_key.get_secret_value()}"},
        )

    def _body(self, system: str, prompt: str, stream: bool) -> dict:
        return {
            "model": self._s.groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._s.llm_max_tokens,
            "temperature": self._s.llm_temperature,
            "stream": stream,
        }

    def _wait(self, response: httpx.Response, attempt: int) -> None:
        if attempt >= self._s.groq_max_retries:
            raise LLMRateLimitedError(f"Groq returned {response.status_code} after retries")
        delay = float(response.headers.get("retry-after", 2 ** attempt))
        log.warning("groq retry", extra={"status": response.status_code, "wait_s": delay})
        time.sleep(min(delay, 60.0))

    def generate(self, system: str, prompt: str) -> str:
        """Return the full answer."""
        for attempt in range(self._s.groq_max_retries + 1):
            r = self._client.post("/chat/completions", json=self._body(system, prompt, False))
            if r.status_code == 429 or r.status_code >= 500:
                self._wait(r, attempt)
                continue
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {})
            log.info("groq call", extra={"model": self._s.groq_model, **usage})
            return data["choices"][0]["message"]["content"] or ""
        raise LLMRateLimitedError("Groq retries exhausted")

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        """Yield answer pieces as they arrive (server-sent events)."""
        for attempt in range(self._s.groq_max_retries + 1):
            with self._client.stream(
                "POST", "/chat/completions", json=self._body(system, prompt, True)
            ) as r:
                if r.status_code == 429 or r.status_code >= 500:
                    r.read()
                    self._wait(r, attempt)
                    continue
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[len("data: ") :]
                    if payload.strip() == "[DONE]":
                        return
                    delta = json.loads(payload)["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]
                return
        raise LLMRateLimitedError("Groq retries exhausted")


def build(settings: Settings) -> GroqLLM:
    """Factory used by the container."""
    return GroqLLM(settings)
