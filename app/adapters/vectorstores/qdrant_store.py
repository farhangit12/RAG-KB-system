"""Qdrant vector store. Install with ``pip install -e ".[qdrant]"``.

Config:
- ``QDRANT_URL=https://...`` (+ ``QDRANT_API_KEY``) for a Qdrant server or Qdrant Cloud;
- ``QDRANT_URL=:memory:`` for an in-process store (tests, demos);
- empty ``QDRANT_URL``: embedded local mode, stored in ``DATA_DIR/qdrant``.

Each point's payload is ``{"chunk_id", "text", "metadata": {...}}``; filters address
``metadata.<key>``. Qdrant needs UUID point ids, so ids are ``uuid5(chunk_id)``.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient, models

from app.core.config import Settings
from app.core.ports import Chunk, Filter, ScoredChunk


def point_id(chunk_id: str) -> str:
    """Stable UUID for a chunk id like ``faq/a.md#0``."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def to_qdrant_filter(where: Filter | None) -> models.Filter | None:
    """Translate our neutral Filter into a Qdrant Filter (all conditions must match)."""
    if not where:
        return None
    must: list[Any] = []
    for key, value in where.items():
        match = (
            models.MatchAny(any=list(value))
            if isinstance(value, list | tuple | set)
            else models.MatchValue(value=value)
        )
        must.append(models.FieldCondition(key=f"metadata.{key}", match=match))
    return models.Filter(must=must)


class QdrantVectorStore:
    """One Qdrant collection, cosine distance. Created on first upsert."""

    def __init__(self, client: QdrantClient, collection: str, batch_size: int = 64) -> None:
        self._client = client
        self._name = collection
        self._batch = batch_size

    def _exists(self) -> bool:
        return self._client.collection_exists(self._name)

    def _ensure(self, size: int) -> None:
        if not self._exists():
            self._client.create_collection(
                self._name,
                vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE),
            )

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace chunks in batches."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        self._ensure(len(embeddings[0]))
        for i in range(0, len(chunks), self._batch):
            points = [
                models.PointStruct(
                    id=point_id(c.id),
                    vector=list(e),
                    payload={
                        "chunk_id": c.id,
                        "text": c.text,
                        "metadata": {**c.metadata, "source": c.source},
                    },
                )
                for c, e in zip(
                    chunks[i : i + self._batch], embeddings[i : i + self._batch], strict=True
                )
            ]
            self._client.upsert(self._name, points=points)

    def delete_by_source(self, source: str) -> None:
        """Remove all chunks of one file."""
        if not self._exists():
            return
        selector = models.FilterSelector(filter=to_qdrant_filter({"source": source}))
        self._client.delete(self._name, points_selector=selector)

    def query(
        self, embedding: Sequence[float], top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Nearest chunks; score is cosine similarity."""
        if not self._exists():
            return []
        res = self._client.query_points(
            self._name,
            query=list(embedding),
            limit=top_k,
            query_filter=to_qdrant_filter(where),
            with_payload=True,
        )
        out = []
        for p in res.points:
            payload = p.payload or {}
            meta = dict(payload.get("metadata", {}))
            chunk = Chunk(
                id=str(payload.get("chunk_id", p.id)),
                source=str(meta.get("source", "")),
                text=str(payload.get("text", "")),
                metadata=meta,
            )
            out.append(ScoredChunk(chunk=chunk, score=float(p.score)))
        return out

    def count(self) -> int:
        """Number of stored chunks."""
        return self._client.count(self._name, exact=True).count if self._exists() else 0

    def reset(self) -> None:
        """Drop the collection (recreated on next upsert)."""
        if self._exists():
            self._client.delete_collection(self._name)


def build(settings: Settings) -> QdrantVectorStore:
    """Factory used by the container."""
    url = settings.qdrant_url.strip()
    if url == ":memory:":
        client = QdrantClient(location=":memory:")
    elif url:
        key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        client = QdrantClient(url=url, api_key=key)
    else:
        path = settings.data_dir / "qdrant"
        path.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(path))
    return QdrantVectorStore(client, settings.collection_public, settings.embed_batch_size)
