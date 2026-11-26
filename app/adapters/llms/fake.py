"""Offline LLM for tests: returns a predictable answer and records every call."""

from __future__ import annotations

from collections.abc import Iterator

from app.core.config import Settings


class FakeLLM:
    """Echoes a short, deterministic answer. ``calls`` keeps (system, prompt) pairs."""

    def __init__(self, reply: str = "FAKE ANSWER") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, prompt: str) -> str:
        """Return the canned reply."""
        self.calls.append((system, prompt))
        return self.reply

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        """Yield the canned reply word by word."""
        words = self.generate(system, prompt).split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else f"{word} "


def build(settings: Settings) -> FakeLLM:
    """Factory used by the container."""
    return FakeLLM()
