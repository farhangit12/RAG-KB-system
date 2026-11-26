"""Token estimate with no dependencies: about 1.3 tokens per word or symbol.

It errs on the high side, so chunks built with it stay under the real limit.
Use ``TOKENIZER=hf`` to count with the bge-m3 tokenizer itself.
"""

from __future__ import annotations

import re

from app.core.config import Settings

_PIECE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class EstimateTokenCounter:
    """Fast, dependency-free token estimate."""

    def count(self, text: str) -> int:
        """Return an upper-side estimate of the token count."""
        return int(len(_PIECE.findall(text)) * 1.3) + 1


def build(settings: Settings) -> EstimateTokenCounter:
    """Factory used by the container."""
    return EstimateTokenCounter()
