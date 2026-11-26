from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from app.adapters.llms import groq
from app.adapters.llms.groq import GroqLLM, LLMRateLimitedError


def _llm(settings, handler) -> GroqLLM:
    s = settings.model_copy(update={"groq_api_key": SecretStr("k"), "groq_max_retries": 1})
    client = httpx.Client(base_url="https://test", transport=httpx.MockTransport(handler))
    return GroqLLM(s, client=client)


def test_generate_retries_after_429(settings, monkeypatch) -> None:
    monkeypatch.setattr(groq.time, "sleep", lambda s: None)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi [S1]"}}],
                                         "usage": {"total_tokens": 10}})

    assert _llm(settings, handler).generate("sys", "q") == "hi [S1]"
    assert calls[0]["messages"][0] == {"role": "system", "content": "sys"}
    assert calls[0]["max_tokens"] == settings.llm_max_tokens


def test_generate_gives_up(settings, monkeypatch) -> None:
    monkeypatch.setattr(groq.time, "sleep", lambda s: None)
    llm = _llm(settings, lambda r: httpx.Response(429))
    with pytest.raises(LLMRateLimitedError):
        llm.generate("s", "q")


def test_stream_reads_server_sent_events(settings) -> None:
    events = [{"choices": [{"delta": {"content": "Hello "}}]},
              {"choices": [{"delta": {"content": "founder"}}]}]
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
    llm = _llm(settings, lambda r: httpx.Response(200, text=body))
    assert "".join(llm.stream("s", "q")) == "Hello founder"


def test_missing_key_is_a_clear_error(settings) -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqLLM(settings)
