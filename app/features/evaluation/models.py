"""Data types for evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvalQuestion(BaseModel):
    """One test question from ``eval/questions.yaml``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_sources: list[str] = Field(default_factory=list)
    stage: Literal["idea", "early", "traction"] | None = None
    sector: str | None = None
    notes: str = ""


@dataclass
class QuestionResult:
    """What happened for one question."""

    item: EvalQuestion
    retrieved: list[str]
    hit_rate: float | None  # None when no sources are expected
    answer: str | None = None
    error: str | None = None

    @property
    def hits(self) -> list[str]:
        """Expected sources that were actually retrieved."""
        return [s for s in self.item.expected_sources if s in self.retrieved]


@dataclass
class EvalReport:
    """All results of one evaluation run."""

    results: list[QuestionResult] = field(default_factory=list)
    report_path: Path | None = None

    @property
    def mean_hit_rate(self) -> float | None:
        """Average hit rate over questions that expect sources."""
        rates = [r.hit_rate for r in self.results if r.hit_rate is not None]
        return sum(rates) / len(rates) if rates else None
