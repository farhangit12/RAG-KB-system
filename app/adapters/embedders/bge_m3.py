"""BAAI/bge-m3 embedder (MIT licence), run locally with sentence-transformers.

One vector of 1,024 numbers per text, normalised, so cosine and dot product agree.
Runs on our own VM: no API cost and no Groq quota. Needs the ``models`` extra.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class BgeM3Embedder:
    """Dense bge-m3 embeddings. bge-m3 needs no query instruction prefix."""

    def __init__(self, model_name: str, device: str, batch_size: int, dim: int) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device=device)
        self._batch_size = batch_size
        actual = self._model.get_sentence_embedding_dimension()
        if actual != dim:
            raise ValueError(f"{model_name} gives {actual}-dim vectors but EMBED_DIM={dim}")
        log.info("embedder loaded", extra={"model": model_name, "dim": actual, "device": device})

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one normalised vector per text."""
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


def build(settings: Settings) -> BgeM3Embedder:
    """Factory used by the container."""
    return BgeM3Embedder(
        settings.embed_model, settings.model_device, settings.embed_batch_size, settings.embed_dim
    )
