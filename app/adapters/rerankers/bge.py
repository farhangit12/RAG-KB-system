"""BAAI/bge-reranker-v2-m3 cross-encoder, run locally. Pairs with bge-m3 embeddings.

Scores are mapped to [0, 1] so one threshold works for all questions. Depending on the
sentence-transformers version, ``predict`` returns logits or already-sigmoided values;
both are handled. Needs the ``models`` extra.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.core.config import Settings


class BgeReranker:
    """Scores (question, chunk) pairs with a cross-encoder."""

    def __init__(self, model_name: str, device: str) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name, device=device, max_length=1024)

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        """Return a [0, 1] relevance score per text."""
        if not texts:
            return []
        raw = [float(x) for x in self._model.predict([(query, t) for t in texts])]
        if all(0.0 <= x <= 1.0 for x in raw):
            return raw
        return [1.0 / (1.0 + math.exp(-x)) for x in raw]


def build(settings: Settings) -> BgeReranker:
    """Factory used by the container."""
    return BgeReranker(settings.rerank_model, settings.model_device)
