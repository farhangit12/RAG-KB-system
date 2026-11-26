"""Data types for retrieval evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    """One test question and the source file(s) that should answer it."""

    question: str
    expected_sources: tuple[str, ...]
    business_id: str | None = None


@dataclass
class CaseResult:
    question: str
    expected: tuple[str, ...]
    got: list[str]
    rank: int | None          # 1-based rank of the first correct chunk, None if missed


@dataclass
class EvalReport:
    """Hit rate at k and mean reciprocal rank (MRR) over all cases."""

    k: int
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        """Share of questions with a correct chunk in the top k."""
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.rank and c.rank <= self.k) / len(self.cases)

    @property
    def mrr(self) -> float:
        """Mean of 1/rank of the first correct chunk (0 when missed)."""
        if not self.cases:
            return 0.0
        return sum(1 / c.rank for c in self.cases if c.rank) / len(self.cases)
