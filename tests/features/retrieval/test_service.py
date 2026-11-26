from __future__ import annotations

from app.core.container import Container
from app.core.ports import Chunk
from app.features.retrieval.service import (
    BusinessProfile,
    access_filters,
    profile_matches,
    retrieve,
)


def _add(container: Container, cid: str, text: str, **meta) -> None:
    meta.setdefault("visibility", "public")
    chunk = Chunk(id=cid, source=cid.split("#")[0], text=text, metadata=meta)
    container.vector_store.upsert([chunk], container.embedder.embed([text]))


def test_private_chunks_only_reach_their_business(container: Container) -> None:
    _add(container, "pub.md#0", "seed funding grant scheme for startups")
    _add(container, "uploads/b1/x.txt#0", "seed funding grant notes for biz one",
         visibility="private", business_id="b1")
    _add(container, "uploads/b2/y.txt#0", "seed funding grant notes for biz two",
         visibility="private", business_id="b2")

    q = "seed funding grant"
    anon = {c.chunk.id for c in retrieve(container, q).ranked}
    b1 = {c.chunk.id for c in retrieve(container, q, BusinessProfile("b1")).ranked}
    assert anon == {"pub.md#0"}
    assert b1 == {"pub.md#0", "uploads/b1/x.txt#0"}


def test_expired_chunks_are_dropped(container: Container) -> None:
    _add(container, "old.md#0", "seed fund scheme details", valid_until="2001-01-01")
    _add(container, "new.md#0", "seed fund scheme details again", valid_until="2999-01-01")
    ids = {c.chunk.id for c in retrieve(container, "seed fund scheme").ranked}
    assert ids == {"new.md#0"}


def test_threshold_gives_not_found(container: Container) -> None:
    _add(container, "a.md#0", "hiring your first employee")
    result = retrieve(container, "quantum chromodynamics lattice")
    assert result.found is False
    assert result.kept == []


def test_keeps_at_most_rerank_keep(container: Container) -> None:
    for i in range(6):
        _add(container, f"p{i}.md#0", f"pricing strategy for startups part {i}")
    result = retrieve(container, "pricing strategy startups")
    assert result.found
    assert len(result.kept) == container.settings.rerank_keep


def test_profile_boost_prefers_matching_sector(container: Container) -> None:
    _add(container, "food.md#0", "pricing strategy guide", sector="foodtech")
    _add(container, "fin.md#0", "pricing strategy guide", sector="fintech")
    profile = BusinessProfile("b1", sector="FoodTech")
    ranked = retrieve(container, "pricing strategy guide", profile).ranked
    assert ranked[0].chunk.id == "food.md#0"


def test_helpers() -> None:
    assert access_filters(None) == [{"visibility": "public"}]
    assert profile_matches({"sector": "all", "location": "rajasthan"},
                           BusinessProfile("b", sector="edtech", location="Rajasthan")) == 2
