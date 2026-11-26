"""Public entry point for retrieval: ``retrieve(container, question)``."""

from __future__ import annotations

from app.core.container import Container
from app.core.ports import Filter, ScoredChunk

__all__ = ["PUBLIC_ONLY", "retrieve"]

PUBLIC_ONLY: dict[str, str] = {"visibility": "public"}


def retrieve(
    container: Container,
    question: str,
    top_k: int | None = None,
    filters: Filter | None = None,
) -> list[ScoredChunk]:
    """Return the most relevant public chunks for ``question``."""
    k = top_k or container.settings.top_k
    where = {**(filters or {}), **PUBLIC_ONLY}
    [vector] = container.embedder.embed([question])
    return container.vector_store.query(vector, top_k=k, where=where)
