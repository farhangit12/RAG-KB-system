"""Claude via the official Anthropic SDK.

With ``LLM_REFUSAL_FALLBACK=true`` the request uses the server-side fallback beta: if the
main model declines on safety grounds, the API reruns the request on a fallback model
inside the same call.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import anthropic

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.ports import LLMError

log = get_logger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
REFUSAL_TEXT = (
    "I can't help with that one here. If it's about your startup, a ₹99 Direction Call "
    "with Sara and Anshuman is the best next step."
)


class AnthropicLLM:
    """Implements the LLM port with Claude."""

    def __init__(
        self,
        client: Any,
        model: str,
        max_tokens: int,
        effort: str,
        refusal_fallback: bool = True,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort
        self._fallback = refusal_fallback

    @property
    def _api(self) -> Any:
        return self._client.beta.messages if self._fallback else self._client.messages

    def _params(self, system: str, prompt: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"effort": self._effort},
        }
        if self._fallback:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def generate(self, system: str, prompt: str) -> str:
        """Return the full answer text."""
        try:
            msg = self._api.create(**self._params(system, prompt))
        except anthropic.APIStatusError as e:
            log.error("llm_error", extra={"status": e.status_code, "request_id": e.request_id})
            raise LLMError(f"Claude API error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            log.error("llm_connection_error")
            raise LLMError("Could not reach the Claude API") from e
        if msg.stop_reason == "refusal":
            log.warning("llm_refusal")
            return REFUSAL_TEXT
        return "".join(b.text for b in msg.content if b.type == "text")

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        """Yield answer text as it is generated."""
        try:
            with self._api.stream(**self._params(system, prompt)) as s:
                yield from s.text_stream
                if s.get_final_message().stop_reason == "refusal":
                    log.warning("llm_refusal")
                    yield f"\n\n{REFUSAL_TEXT}"
        except anthropic.APIStatusError as e:
            log.error("llm_error", extra={"status": e.status_code, "request_id": e.request_id})
            raise LLMError(f"Claude API error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            log.error("llm_connection_error")
            raise LLMError("Could not reach the Claude API") from e


def build(settings: Settings) -> AnthropicLLM:
    """Factory used by the container. The key comes only from settings / env."""
    key = settings.anthropic_api_key
    client = anthropic.Anthropic(api_key=key.get_secret_value()) if key else anthropic.Anthropic()
    return AnthropicLLM(
        client,
        model=settings.anthropic_model,
        max_tokens=settings.llm_max_tokens,
        effort=settings.llm_effort,
        refusal_fallback=settings.llm_refusal_fallback,
    )
