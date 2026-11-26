"""Chroma's default local embedding model (all-MiniLM-L6-v2 via ONNX), behind our port.

The model (~80 MB) downloads on first use into the user's cache folder.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import Settings


class ChromaDefaultEmbedder:
    """Wraps ``chromadb``'s DefaultEmbeddingFunction."""

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        self._fn = DefaultEmbeddingFunction()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text."""
        if not texts:
            return []
        return [[float(x) for x in vec] for vec in self._fn(list(texts))]


def build(settings: Settings) -> ChromaDefaultEmbedder:
    """Factory used by the container."""
    return ChromaDefaultEmbedder()
