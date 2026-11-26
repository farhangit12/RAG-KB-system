"""Tests the Claude adapter against a stand-in client: no network, no API key."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.adapters.llms.anthropic_llm import FALLBACK_BETA, REFUSAL_TEXT, AnthropicLLM
from app.core.ports import LLMError


def _message(text: str, stop_reason: str = "end_turn") -> Any:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
    )


class _Messages:
    def __init__(self, reply: Any = None, error: Exception | None = None) -> None:
        self.reply, self.error, self.calls = reply, error, []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.reply

    @contextmanager
    def stream(self, **kwargs: Any) -> Iterator[Any]:
        self.calls.append(kwargs)
        yield SimpleNamespace(
            text_stream=iter(["Hello ", "founder"]),
            get_final_message=lambda: self.reply,
        )


def _llm(messages: _Messages, fallback: bool = True) -> AnthropicLLM:
    client = SimpleNamespace(messages=messages, beta=SimpleNamespace(messages=messages))
    return AnthropicLLM(client, "claude-sonnet-5-5", 1000, "medium", refusal_fallback=fallback)


def test_generate_sends_expected_params_and_joins_text() -> None:
    msgs = _Messages(reply=_message("Talk to ten real people."))
    assert _llm(msgs).generate("SYS", "PROMPT") == "Talk to ten real people."
    [call] = msgs.calls
    assert call["model"] == "claude-sonnet-5-5"
    assert call["system"] == "SYS"
    assert call["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert call["output_config"] == {"effort": "medium"}
    assert call["betas"] == [FALLBACK_BETA]
    assert call["fallbacks"] == "default"


def test_no_fallback_params_when_disabled() -> None:
    msgs = _Messages(reply=_message("ok"))
    _llm(msgs, fallback=False).generate("S", "P")
    assert "betas" not in msgs.calls[0]
    assert "fallbacks" not in msgs.calls[0]


def test_refusal_returns_friendly_text() -> None:
    msgs = _Messages(reply=_message("", stop_reason="refusal"))
    assert _llm(msgs).generate("S", "P") == REFUSAL_TEXT


def test_stream_yields_text() -> None:
    msgs = _Messages(reply=_message("Hello founder"))
    assert "".join(_llm(msgs).stream("S", "P")) == "Hello founder"


def test_api_errors_become_llm_error() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.APIConnectionError(request=request)
    with pytest.raises(LLMError):
        _llm(_Messages(error=err)).generate("S", "P")
