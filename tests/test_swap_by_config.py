"""Proves the vector store can be swapped with settings alone: no feature code changes."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.container import Container
from app.features.chat.service import answer
from app.features.ingestion.service import ingest
from app.features.retrieval.service import QueryFilters


@pytest.mark.parametrize(
    "store_settings",
    [
        {"vector_store": "memory"},
        {"vector_store": "chroma"},
        {"vector_store": "qdrant", "qdrant_url": ":memory:"},
        {"vector_store": "qdrant", "qdrant_url": ""},  # embedded local files
    ],
    ids=["memory", "chroma", "qdrant-memory", "qdrant-local"],
)
def test_same_pipeline_on_every_store(
    settings: Settings, content_copy, store_settings: dict
) -> None:
    c = Container(settings.model_copy(update={"content_dir": content_copy, **store_settings}))
    report = ingest(c)
    assert len(report.added) == 4

    result = answer(c, "How do I talk to ten real people?")
    assert result.sources[0].source == "frameworks/disha-path.md"

    faq_only = answer(c, "anything", filters=QueryFilters(type=["faq"]))
    assert {s.source for s in faq_only.sources} == {"faq/direction-call.md"}

    again = ingest(c)
    assert len(again.unchanged) == 4
