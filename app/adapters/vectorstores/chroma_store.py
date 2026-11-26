"""Persistent local vector store using Chroma. We pass our own embeddings."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.ports import Chunk, Filter, ScoredChunk


def to_chroma_where(where: Filter | None) -> dict[str, Any] | None:
    """Translate our neutral Filter into Chroma's ``where`` syntax."""
    if not where:
        return None
    conds: list[dict[str, Any]] = [
        {k: {"$in": list(v)}} if isinstance(v, list | tuple | set) else {k: {"$eq": v}}
        for k, v in where.items()
    ]
    return conds[0] if len(conds) == 1 else {"$and": conds}


class ChromaVectorStore:
    """One Chroma collection on disk, cosine distance."""

    def __init__(self, path: Path, collection: str, batch_size: int = 64) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._name = collection
        self._batch = batch_size
        self._col = self._open()

    def _open(self) -> Any:
        return self._client.get_or_create_collection(
            self._name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
        )

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace chunks in batches."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        for i in range(0, len(chunks), self._batch):
            part = chunks[i : i + self._batch]
            self._col.upsert(
                ids=[c.id for c in part],
                embeddings=[list(e) for e in embeddings[i : i + self._batch]],
                documents=[c.text for c in part],
                metadatas=[{**c.metadata, "source": c.source} for c in part],
            )

    def delete_by_source(self, source: str) -> None:
        """Remove all chunks of one file."""
        self._col.delete(where={"source": {"$eq": source}})

    def query(
        self, embedding: Sequence[float], top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Nearest chunks; score is cosine similarity (1 - distance)."""
        if self._col.count() == 0:
            return []
        res = self._col.query(
            query_embeddings=[list(embedding)],
            n_results=top_k,
            where=to_chroma_where(where),
            include=["documents", "metadatas", "distances"],
        )
        out: list[ScoredChunk] = []
        for cid, doc, meta, dist in zip(
            res["ids"][0],
            res["documents"][0],
            res["metadatas"][0],
            res["distances"][0],
            strict=True,
        ):
            meta = dict(meta or {})
            chunk = Chunk(id=cid, source=str(meta.get("source", "")), text=doc or "", metadata=meta)
            out.append(ScoredChunk(chunk=chunk, score=1.0 - float(dist)))
        return out

    def count(self) -> int:
        """Number of stored chunks."""
        return self._col.count()

    def reset(self) -> None:
        """Drop and recreate the collection."""
        self._client.delete_collection(self._name)
        self._col = self._open()


def build(settings: Settings) -> ChromaVectorStore:
    """Factory used by the container."""
    return ChromaVectorStore(
        settings.data_dir / "chroma", settings.collection_public, settings.embed_batch_size
    )
