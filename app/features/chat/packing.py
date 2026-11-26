"""Packing: turn the reranked chunks into labelled sources that fit the token budget.

Order: highest rerank score first; on near-ties the newer source wins (market reports and
datasets go stale). Each source gets a label ([S1]...) and a citation line built from its
metadata: title, page, publisher and year.
"""

from __future__ import annotations

from app.core.ports import Chunk, TokenCounter
from app.features.chat.models import Source

TIE_MARGIN = 0.02


def citation(chunk: Chunk) -> str:
    """Human-readable citation, e.g. ``Startup India Seed Fund, p. 4, DPIIT 2025``."""
    m = chunk.metadata
    parts = [str(m.get("title") or chunk.source)]
    if m.get("page_start"):
        same = m.get("page_end") in (None, m.get("page_start"))
        parts.append(f"p. {m['page_start']}" if same else f"pp. {m['page_start']}-{m['page_end']}")
    year = m.get("publication_year") or (str(m["date"])[:4] if m.get("date") else None)
    who = " ".join(str(x) for x in (m.get("publisher"), year) if x)
    if who:
        parts.append(who)
    return ", ".join(parts)


def _year(chunk: Chunk) -> int:
    m = chunk.metadata
    raw = m.get("publication_year") or (str(m.get("date"))[:4] if m.get("date") else 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def order(scored: list[tuple[Chunk, float]]) -> list[tuple[Chunk, float]]:
    """Best score first; within TIE_MARGIN, newer first."""
    items = sorted(scored, key=lambda x: x[1], reverse=True)
    for i in range(len(items) - 1):
        a, b = items[i], items[i + 1]
        if a[1] - b[1] <= TIE_MARGIN and _year(b[0]) > _year(a[0]):
            items[i], items[i + 1] = b, a
    return items


def pack(scored: list[tuple[Chunk, float]], count: TokenCounter, budget: int) -> list[Source]:
    """Label and add whole chunks until the token budget is used; never split a chunk."""
    sources: list[Source] = []
    used = 0
    for chunk, score in order(scored):
        label = f"S{len(sources) + 1}"
        cite = citation(chunk)
        cost = count.count(f"[{label}] {cite}\n{chunk.text}")
        if sources and used + cost > budget:
            break
        used += cost
        sources.append(Source(label, chunk.id, chunk.source, cite, chunk.text, score))
    return sources
