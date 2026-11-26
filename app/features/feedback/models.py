"""Data types for feedback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Rating = Literal["up", "down"]


@dataclass(frozen=True)
class FeedbackRecord:
    """One rating of one answer. No personal data (IP, name) is stored."""

    question: str
    answer: str
    rating: Rating
    sources: list[str] = field(default_factory=list)
    comment: str | None = None
    created_at: str = ""
    id: int | None = None
