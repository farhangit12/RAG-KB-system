"""Offline reranker for tests: share of question words found in the text."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.core.config import Settings

_WORD = re.compile(r"[a-z0-9]+")


class FakeReranker:
    """Word-overlap score in [0, 1]. Deterministic."""

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        """Return the fraction of query words that appear in each text."""
        q = {w for w in _WORD.findall(query.lower()) if len(w) > 2}
        if not q:
            return [0.0 for _ in texts]
        return [len(q & set(_WORD.findall(t.lower()))) / len(q) for t in texts]


def build(settings: Settings) -> FakeReranker:
    """Factory used by the container."""
    return FakeReranker()
