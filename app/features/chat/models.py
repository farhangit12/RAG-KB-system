"""Data types for the chat (answer generation) slice."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """One packed source, shown to the model as [S1], [S2], ..."""

    label: str
    chunk_id: str
    source: str
    citation: str      # e.g. "Seed Fund guide, p. 4, 2025"
    text: str
    score: float


@dataclass
class AnswerResult:
    """The answer plus everything needed to show and audit it."""

    answer: str
    found: bool
    sources: list[Source] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    low_confidence: bool = False
    prompt_tokens: int = 0
