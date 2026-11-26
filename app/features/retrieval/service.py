"""Public entry point for retrieval: ``retrieve(container, question)``.

Steps: embed the question -> fetch ``RETRIEVAL_CANDIDATES`` public chunks -> boost the
ones matching the asker's stage/sector -> keep the top ``TOP_K`` -> make sure the Disha
Path framework is included when it is relevant enough.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.container import Container
from app.core.ports import Filter, ScoredChunk
from app.features.retrieval.models import QueryFilters, UserContext
from app.features.retrieval.personalize import BoostWeights, boost, pin

__all__ = ["PUBLIC_ONLY", "QueryFilters", "UserContext", "retrieve"]

PUBLIC_ONLY: dict[str, str] = {"visibility": "public"}


def _disha_path(container: Container, vector: Sequence[float], where: Filter) -> ScoredChunk | None:
    s = container.settings
    if not s.disha_path_source:
        return None
    hits = container.vector_store.query(
        vector, top_k=1, where={**where, "source": s.disha_path_source}
    )
    return hits[0] if hits and hits[0].score >= s.disha_path_min_score else None


def retrieve(
    container: Container,
    question: str,
    top_k: int | None = None,
    filters: QueryFilters | None = None,
    context: UserContext | None = None,
) -> list[ScoredChunk]:
    """Return the most relevant public chunks for ``question``, personalised to ``context``.

    ``visibility=public`` is always enforced, whatever filters are passed.
    """
    s = container.settings
    k = top_k or s.top_k
    where = {**(filters.to_filter() if filters else {}), **PUBLIC_ONLY}
    [vector] = container.embedder.embed([question])
    candidates = container.vector_store.query(
        vector, top_k=max(k, s.retrieval_candidates), where=where
    )
    ranked = boost(candidates, context, BoostWeights(s.boost_stage, s.boost_sector))
    return pin(ranked, _disha_path(container, vector, where), k)
