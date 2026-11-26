"""Exact token counts with the embedding model's own tokenizer (bge-m3 uses XLM-RoBERTa).

Needs the ``models`` extra (transformers comes with sentence-transformers).
"""

from __future__ import annotations

from app.core.config import Settings


class HFTokenCounter:
    """Counts tokens with a Hugging Face tokenizer."""

    def __init__(self, model_name: str) -> None:
        from transformers import AutoTokenizer

        self._tok = AutoTokenizer.from_pretrained(model_name)

    def count(self, text: str) -> int:
        """Return the exact token count, without special tokens."""
        return len(self._tok.encode(text, add_special_tokens=False))


def build(settings: Settings) -> HFTokenCounter:
    """Factory used by the container."""
    return HFTokenCounter(settings.embed_model)
