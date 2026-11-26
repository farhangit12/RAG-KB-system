"""Deterministic offline embedder for tests and local runs without models.

Each word is hashed into one of ``dim`` buckets, then the vector is normalised.
Texts sharing words end up close together, which is enough to test retrieval.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from app.core.config import Settings

_WORD = re.compile(r"[a-z0-9]+")


class FakeEmbedder:
    """Bag-of-words hashing embedder. Same input always gives the same vector."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one unit-length vector per text."""
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in _WORD.findall(text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def build(settings: Settings) -> FakeEmbedder:
    """Factory used by the container."""
    return FakeEmbedder()
