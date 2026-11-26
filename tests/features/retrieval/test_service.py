from __future__ import annotations

import pytest

from app.core.container import Container
from app.core.ports import Chunk
from app.features.ingestion.service import ingest
from app.features.retrieval.service import QueryFilters, retrieve


@pytest.fixture
def indexed(tmp_container: Container) -> Container:
    ingest(tmp_container)
    return tmp_container


def _sources(hits: list) -> set[str]:
    return {h.chunk.source for h in hits}


def test_filter_by_type(indexed: Container) -> None:
    hits = retrieve(indexed, "Disha Path", top_k=20, filters=QueryFilters(type=["faq"]))
    assert _sources(hits) == {"faq/direction-call.md"}


def test_filter_by_stage_and_sector(indexed: Container) -> None:
    hits = retrieve(
        indexed, "pitch", top_k=20, filters=QueryFilters(stage=["early"], sector=["social-impact"])
    )
    assert _sources(hits) == {"case-studies/bhumi.md"}


def test_filter_any_of_types(indexed: Container) -> None:
    hits = retrieve(indexed, "x", top_k=50, filters=QueryFilters(type=["faq", "story"]))
    assert _sources(hits) == {"faq/direction-call.md", "stories/sara-and-anshuman.md"}


def test_filter_by_person_and_topic_flags(indexed: Container) -> None:
    hits = retrieve(indexed, "x", top_k=50, filters=QueryFilters(people=["Sara"], topics=["pitch"]))
    assert _sources(hits) == {"case-studies/bhumi.md"}


def test_internal_chunks_never_returned(indexed: Container) -> None:
    leaked = Chunk("x.md#0", "x.md", "Disha Path secret", {"visibility": "internal"})
    indexed.vector_store.upsert([leaked], indexed.embedder.embed([leaked.text]))
    hits = retrieve(indexed, "Disha Path secret", top_k=50)
    assert "x.md" not in _sources(hits)


def test_query_filters_translation() -> None:
    f = QueryFilters(type=["faq"], stage=["idea", "early"], people=["Sara"]).to_filter()
    assert f == {"type": "faq", "founder_stage": ["idea", "early"], "people_sara": True}
