"""Public entry point for retrieval: ``retrieve(container, question)``."""

from __future__ import annotations

from app.core.container import Container
from app.core.ports import ScoredChunk
from app.features.retrieval.models import QueryFilters, UserContext

__all__ = ["PUBLIC_ONLY", "QueryFilters", "UserContext", "retrieve"]

PUBLIC_ONLY: dict[str, str] = {"visibility": "public"}


def retrieve(
    container: Container,
    question: str,
    top_k: int | None = None,
    filters: QueryFilters | None = None,
) -> list[ScoredChunk]:
    """Return the most relevant public chunks for ``question``.

    ``visibility=public`` is always enforced, whatever filters are passed.
    """
    k = top_k or container.settings.top_k
    where = {**(filters.to_filter() if filters else {}), **PUBLIC_ONLY}
    [vector] = container.embedder.embed([question])
    return container.vector_store.query(vector, top_k=k, where=where)
