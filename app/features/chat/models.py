"""Data types for chat answers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceRef:
    """A cited source: one per content file, best score kept."""

    title: str
    source: str
    type: str
    score: float


@dataclass(frozen=True)
class Answer:
    """The model's answer plus the sources it was given."""

    text: str
    sources: list[SourceRef] = field(default_factory=list)
