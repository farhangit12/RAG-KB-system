"""Re-rank candidates for the asker, and keep the Disha Path in view when it's relevant."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.core.ports import ScoredChunk
from app.features.retrieval.models import UserContext


@dataclass(frozen=True)
class BoostWeights:
    """How much a metadata match adds to the similarity score."""

    stage: float = 0.10
    sector: float = 0.10


def _norm(value: object) -> str:
    return str(value).strip().lower()


def boost(
    chunks: Sequence[ScoredChunk], context: UserContext | None, weights: BoostWeights
) -> list[ScoredChunk]:
    """Add the configured bonus when a chunk's stage/sector match the asker; re-sort."""
    if not context or not (context.stage or context.sector):
        return sorted(chunks, key=lambda c: c.score, reverse=True)
    out = []
    for sc in chunks:
        meta = sc.chunk.metadata
        bonus = 0.0
        if context.stage and _norm(meta.get("founder_stage", "")) == _norm(context.stage):
            bonus += weights.stage
        if context.sector and _norm(meta.get("sector", "")) == _norm(context.sector):
            bonus += weights.sector
        out.append(replace(sc, score=sc.score + bonus))
    return sorted(out, key=lambda c: c.score, reverse=True)


def pin(
    results: Sequence[ScoredChunk], pinned: ScoredChunk | None, top_k: int
) -> list[ScoredChunk]:
    """Ensure ``pinned`` is in the top ``top_k`` (replacing the last one) if its file is absent."""
    head = list(results[:top_k])
    if pinned is None or any(r.chunk.source == pinned.chunk.source for r in head):
        return head
    return [*head[: top_k - 1], pinned]
