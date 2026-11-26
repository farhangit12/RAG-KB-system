"""Chroma vector store: optional, for running the KB on a laptop without Oracle.

Persists under ``DATA_DIR/chroma``. Vector search only (no keyword search), so retrieval
falls back to vector results alone. Needs the ``chroma`` extra.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from app.core.config import Settings
from app.core.ports import Chunk, Filter, ScoredChunk


def chroma_where(where: Filter | None) -> dict[str, Any] | None:
    """Translate a ports.Filter into Chroma's ``where`` syntax."""
    if not where:
        return None
    clauses = []
    for key, expected in where.items():
        if isinstance(expected, list | tuple | set):
            clauses.append({key: {"$in": list(expected)}})
        else:
            clauses.append({key: {"$eq": expected}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class ChromaVectorStore:
    """VectorStore + Exportable backed by a persistent Chroma collection."""

    def __init__(self, settings: Settings) -> None:
        import chromadb

        path = settings.data_dir / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(path))
        self._col = client.get_or_create_collection(
            settings.collection_public, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace chunks by id."""
        if not chunks:
            return
        self._col.upsert(
            ids=[c.id for c in chunks],
            embeddings=[list(e) for e in embeddings],
            documents=[c.text for c in chunks],
            metadatas=[{**c.metadata, "source": c.source} for c in chunks],
        )

    def delete_by_source(self, source: str) -> None:
        """Remove every chunk from one source."""
        self._col.delete(where={"source": {"$eq": source}})

    def query(
        self, embedding: Sequence[float], top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Cosine search; score = 1 - distance."""
        res = self._col.query(
            query_embeddings=[list(embedding)], n_results=top_k, where=chroma_where(where)
        )
        out = []
        for cid, text, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0],
            strict=True,
        ):
            meta = dict(meta or {})
            out.append(ScoredChunk(Chunk(cid, str(meta.get("source", "")), text, meta), 1 - dist))
        return out

    def export_items(self) -> Iterator[tuple[Chunk, list[float]]]:
        """Yield every chunk with its vector."""
        res = self._col.get(include=["documents", "metadatas", "embeddings"])
        for cid, text, meta, emb in zip(
            res["ids"], res["documents"], res["metadatas"], res["embeddings"], strict=True
        ):
            meta = dict(meta or {})
            yield Chunk(cid, str(meta.get("source", "")), text, meta), list(emb)

    def count(self) -> int:
        """Number of stored chunks."""
        return self._col.count()


def build(settings: Settings) -> ChromaVectorStore:
    """Factory used by the container."""
    return ChromaVectorStore(settings)
