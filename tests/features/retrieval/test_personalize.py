from __future__ import annotations

from app.core.config import Settings
from app.core.container import Container
from app.core.ports import Chunk, ScoredChunk
from app.features.ingestion.service import ingest
from app.features.retrieval.personalize import BoostWeights, boost, pin
from app.features.retrieval.service import QueryFilters, UserContext, retrieve


def _sc(source: str, score: float, **meta: str) -> ScoredChunk:
    return ScoredChunk(Chunk(f"{source}#0", source, "t", dict(meta)), score)


def test_boost_reorders_by_stage_and_sector() -> None:
    chunks = [
        _sc("a.md", 0.50, founder_stage="traction", sector="edtech"),
        _sc("b.md", 0.45, founder_stage="idea", sector="health"),
    ]
    ranked = boost(chunks, UserContext(stage="idea"), BoostWeights(stage=0.1, sector=0.1))
    assert [c.chunk.source for c in ranked] == ["b.md", "a.md"]
    assert round(ranked[0].score, 2) == 0.55

    both = boost(chunks, UserContext(stage="Idea", sector="HEALTH"), BoostWeights(0.1, 0.1))
    assert round(both[0].score, 2) == 0.65  # case-insensitive, both bonuses


def test_boost_without_context_only_sorts() -> None:
    chunks = [_sc("a.md", 0.1), _sc("b.md", 0.9)]
    assert [c.chunk.source for c in boost(chunks, None, BoostWeights())] == ["b.md", "a.md"]


def test_pin_replaces_last_only_when_missing() -> None:
    results = [_sc("a.md", 0.9), _sc("b.md", 0.8), _sc("c.md", 0.7)]
    dp = _sc("frameworks/disha-path.md", 0.4)
    assert [r.chunk.source for r in pin(results, dp, 3)] == ["a.md", "b.md", dp.chunk.source]
    assert pin([*results[:2], dp], dp, 3) == [*results[:2], dp]
    assert pin(results, None, 2) == results[:2]


def _container(base: Container, **updates: object) -> Container:
    c = Container(base.settings.model_copy(update=updates))
    c.__dict__["vector_store"] = base.vector_store
    return c


def test_disha_path_pinned_when_relevant(tmp_container: Container) -> None:
    ingest(tmp_container)
    q = "What is a Direction Call?"
    always = _container(tmp_container, top_k=1, disha_path_min_score=0.0)
    assert [h.chunk.source for h in retrieve(always, q)] == ["frameworks/disha-path.md"]

    never = _container(tmp_container, top_k=1, disha_path_min_score=1.01)
    assert [h.chunk.source for h in retrieve(never, q)] == ["faq/direction-call.md"]

    disabled = _container(tmp_container, top_k=1, disha_path_source="", disha_path_min_score=0.0)
    assert [h.chunk.source for h in retrieve(disabled, q)] == ["faq/direction-call.md"]


def test_pin_respects_filters(tmp_container: Container) -> None:
    ingest(tmp_container)
    c = _container(tmp_container, disha_path_min_score=0.0)
    hits = retrieve(c, "anything", filters=QueryFilters(type=["faq"]))
    assert {h.chunk.source for h in hits} == {"faq/direction-call.md"}


def test_context_boost_changes_ranking_end_to_end(tmp_container: Container) -> None:
    ingest(tmp_container)
    c = _container(tmp_container, boost_sector=5.0, disha_path_source="")
    hits = retrieve(c, "Direction Call", context=UserContext(sector="social-impact"))
    assert hits[0].chunk.source == "case-studies/bhumi.md"


def test_weights_are_configurable() -> None:
    s = Settings(_env_file=None, boost_stage=0.3, boost_sector=0.0)
    assert (s.boost_stage, s.boost_sector) == (0.3, 0.0)
