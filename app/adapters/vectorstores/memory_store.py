"""In-memory VectorStore. Not persistent; used for tests and as a reference adapter."""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.core.config import Settings
from app.core.ports import Chunk, Filter, MetadataValue, ScoredChunk


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def matches(metadata: dict[str, MetadataValue], where: Filter | None) -> bool:
    """True if metadata satisfies every condition in ``where`` (see ports.Filter)."""
    if not where:
        return True
    for key, expected in where.items():
        value = metadata.get(key)
        if isinstance(expected, list | tuple | set):
            if value not in expected:
                return False
        elif value != expected:
            return False
    return True


class MemoryVectorStore:
    """Keeps chunks and vectors in a dict keyed by chunk id."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[Chunk, list[float]]] = {}

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace chunks by id."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        for chunk, emb in zip(chunks, embeddings, strict=True):
            self._items[chunk.id] = (chunk, list(emb))

    def delete_by_source(self, source: str) -> None:
        """Remove all chunks from ``source``."""
        self._items = {k: v for k, v in self._items.items() if v[0].source != source}

    def query(
        self, embedding: Sequence[float], top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Brute-force cosine search over matching chunks."""
        scored = [
            ScoredChunk(chunk=chunk, score=_cosine(embedding, emb))
            for chunk, emb in self._items.values()
            if matches(chunk.metadata, where)
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        """Number of stored chunks."""
        return len(self._items)

    def reset(self) -> None:
        """Remove everything."""
        self._items.clear()


def build(settings: Settings) -> MemoryVectorStore:
    """Factory used by the container."""
    return MemoryVectorStore()
