"""Data types for the retrieval slice."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.ports import Chunk


@dataclass(frozen=True)
class BusinessProfile:
    """The asking business (from the main app's profile DB). All fields optional except id.

    ``business_id`` unlocks that business's private files. The other fields make
    answers specific to its industry, stage and location (enhancement 6).
    """

    business_id: str
    sector: str | None = None
    founder_stage: str | None = None
    location: str | None = None
    business_model: str | None = None
    target_audience: str | None = None
    summary: str | None = None


@dataclass
class Candidate:
    """A chunk on its way through fusion and reranking."""

    chunk: Chunk
    vector_rank: int | None = None
    keyword_rank: int | None = None
    fused: float = 0.0
    profile_matches: int = 0
    rerank: float | None = None


@dataclass
class RetrievalResult:
    """Ranked chunks after reranking. ``found`` is False when nothing passed the threshold."""

    kept: list[Candidate] = field(default_factory=list)
    ranked: list[Candidate] = field(default_factory=list)   # all reranked, best first
    found: bool = False
