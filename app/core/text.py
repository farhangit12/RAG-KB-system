"""Small text helpers shared by adapters and features (no external libraries)."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    {
        "the", "and", "for", "are", "was", "with", "that", "this", "from", "have", "what",
        "which", "how", "can", "our", "your", "you", "should", "would", "could", "does",
        "into", "about", "will", "when", "where", "who", "why", "there", "their", "them",
        "kya", "hai", "hum", "kar", "aur", "mein", "liye", "nahi", "koi", "kaise", "kaun",
    }
)
_TERM = re.compile(r"[a-z0-9ऀ-ॿ]+")


def keyword_terms(text: str, max_terms: int = 12) -> list[str]:
    """Meaningful lower-case words of ``text`` for keyword search, in order, no repeats."""
    seen: set[str] = set()
    out: list[str] = []
    for word in _TERM.findall(text.lower()):
        if len(word) >= 3 and word not in STOPWORDS and word not in seen:
            seen.add(word)
            out.append(word)
    return out[:max_terms]
