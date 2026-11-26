"""Retrieval: question -> hybrid search -> filter -> fuse -> personalise -> rerank -> top 3.

1. Embed the question (bge-m3).
2. Search public chunks, plus the asking business's private chunks, by meaning
   (vector) and by exact words (keyword search, when the store supports it).
   The access rule is applied in the store query, never left to the prompt.
3. Drop expired chunks (``valid_until`` in the past).
4. Fuse the ranked lists with reciprocal rank fusion (RRF).
5. Boost chunks that match the business's sector, stage and location.
6. Rerank the top candidates with a cross-encoder and keep the best RERANK_KEEP
   whose score is at least RERANK_MIN_SCORE. If none pass, ``found`` is False.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from app.core.container import Container
from app.core.logging import get_logger
from app.core.ports import Filter, KeywordSearch, ScoredChunk
from app.features.retrieval.models import BusinessProfile, Candidate, RetrievalResult

__all__ = ["BusinessProfile", "Candidate", "RetrievalResult", "access_filters", "retrieve"]

log = get_logger(__name__)

PROFILE_FIELDS = ("sector", "founder_stage", "location")
WILDCARDS = {"all", "any", "general"}


def is_expired(metadata: dict, today: dt.date | None = None) -> bool:
    """True when ``valid_until`` is set and in the past (expired schemes, old offers)."""
    value = metadata.get("valid_until")
    if not isinstance(value, str):
        return False
    try:
        return dt.date.fromisoformat(value) < (today or dt.date.today())
    except ValueError:
        return False


def access_filters(profile: BusinessProfile | None) -> list[Filter]:
    """Public chunks for everyone, plus private chunks of the asking business only."""
    filters: list[Filter] = [{"visibility": "public"}]
    if profile and profile.business_id:
        filters.append({"visibility": "private", "business_id": profile.business_id})
    return filters


def _merge(lists: Sequence[list[ScoredChunk]]) -> list[ScoredChunk]:
    by_id: dict[str, ScoredChunk] = {}
    for hits in lists:
        for h in hits:
            if h.chunk.id not in by_id or h.score > by_id[h.chunk.id].score:
                by_id[h.chunk.id] = h
    return sorted(by_id.values(), key=lambda h: h.score, reverse=True)


def profile_matches(metadata: dict, profile: BusinessProfile | None) -> int:
    """How many of sector, stage and location match the business (wildcards count)."""
    if profile is None:
        return 0
    n = 0
    for name in PROFILE_FIELDS:
        wanted = getattr(profile, name)
        have = metadata.get(name)
        if not wanted or not isinstance(have, str):
            continue
        values = {v.strip().lower() for v in have.split(",")}
        if wanted.strip().lower() in values or values & WILDCARDS:
            n += 1
    return n


def fuse(
    vector_hits: list[ScoredChunk],
    keyword_hits: list[ScoredChunk],
    rrf_k: int,
    profile: BusinessProfile | None,
    boost: float,
) -> list[Candidate]:
    """Reciprocal rank fusion, then a small multiplicative bonus per profile match."""
    cands: dict[str, Candidate] = {}
    for rank, h in enumerate(vector_hits, start=1):
        c = cands.setdefault(h.chunk.id, Candidate(h.chunk))
        c.vector_rank = rank
        c.fused += 1.0 / (rrf_k + rank)
    for rank, h in enumerate(keyword_hits, start=1):
        c = cands.setdefault(h.chunk.id, Candidate(h.chunk))
        c.keyword_rank = rank
        c.fused += 1.0 / (rrf_k + rank)
    for c in cands.values():
        c.profile_matches = profile_matches(c.chunk.metadata, profile)
        c.fused *= 1.0 + boost * c.profile_matches
    return sorted(cands.values(), key=lambda c: c.fused, reverse=True)


def retrieve(
    container: Container, question: str, profile: BusinessProfile | None = None
) -> RetrievalResult:
    """Return the best chunks for ``question`` that this business is allowed to see."""
    s = container.settings
    store = container.vector_store
    filters = access_filters(profile)

    qvec = container.embedder.embed([question])[0]
    vector_hits = _merge([store.query(qvec, s.top_k, where=f) for f in filters])
    keyword_hits: list[ScoredChunk] = []
    if isinstance(store, KeywordSearch):
        keyword_hits = _merge([store.keyword_query(question, s.top_k, where=f) for f in filters])

    vector_hits = [h for h in vector_hits if not is_expired(h.chunk.metadata)]
    keyword_hits = [h for h in keyword_hits if not is_expired(h.chunk.metadata)]

    candidates = fuse(vector_hits, keyword_hits, s.rrf_k, profile, s.profile_boost)[: s.top_k]
    if not candidates:
        return RetrievalResult()

    scores = container.reranker.score(question, [c.chunk.text for c in candidates])
    for c, sc in zip(candidates, scores, strict=True):
        c.rerank = sc
    ranked = sorted(candidates, key=lambda c: (c.rerank or 0.0, c.fused), reverse=True)
    kept = [c for c in ranked if (c.rerank or 0.0) >= s.rerank_min_score][: s.rerank_keep]
    log.info(
        "retrieved",
        extra={"candidates": len(candidates), "kept": len(kept),
               "best": round(ranked[0].rerank or 0.0, 3)},
    )
    return RetrievalResult(kept=kept, ranked=ranked, found=bool(kept))
