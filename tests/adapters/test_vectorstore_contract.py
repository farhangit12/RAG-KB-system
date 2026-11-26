"""The same behaviour test runs against every VectorStore adapter.

If an adapter passes this file, feature code can use it with a config change only.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.adapters.embedders.fake import FakeEmbedder
from app.adapters.vectorstores.chroma_store import ChromaVectorStore, to_chroma_where
from app.adapters.vectorstores.memory_store import MemoryVectorStore
from app.adapters.vectorstores.qdrant_store import QdrantVectorStore, point_id
from app.core.ports import Chunk, VectorStore

StoreFactory = Callable[[Path], VectorStore]

FACTORIES: dict[str, StoreFactory] = {
    "memory": lambda _: MemoryVectorStore(),
    "chroma": lambda p: ChromaVectorStore(p / "chroma", "contract_test", batch_size=2),
    "qdrant": lambda _: QdrantVectorStore(QdrantClient(location=":memory:"), "contract_test", 2),
}


@pytest.fixture(params=sorted(FACTORIES))
def store(request: pytest.FixtureRequest, tmp_path: Path) -> VectorStore:
    return FACTORIES[request.param](tmp_path)


EMB = FakeEmbedder()
CHUNKS = [
    Chunk("faq/a.md#0", "faq/a.md", "book a direction call", {"type": "faq", "source": "faq/a.md"}),
    Chunk("faq/a.md#1", "faq/a.md", "direction call price", {"type": "faq", "source": "faq/a.md"}),
    Chunk(
        "stories/b.md#0",
        "stories/b.md",
        "waterpro failed",
        {"type": "story", "founder_stage": "idea", "source": "stories/b.md"},
    ),
]


def _fill(store: VectorStore) -> None:
    store.upsert(CHUNKS, EMB.embed([c.text for c in CHUNKS]))


def test_upsert_count_and_query(store: VectorStore) -> None:
    _fill(store)
    assert store.count() == 3
    hits = store.query(EMB.embed(["direction call"])[0], top_k=2)
    assert {h.chunk.id for h in hits} == {"faq/a.md#0", "faq/a.md#1"}
    assert hits[0].score >= hits[1].score
    assert hits[0].chunk.metadata["type"] == "faq"
    assert hits[0].chunk.text


def test_filters(store: VectorStore) -> None:
    _fill(store)
    q = EMB.embed(["direction call"])[0]
    assert {h.chunk.source for h in store.query(q, 5, {"type": "story"})} == {"stories/b.md"}
    assert len(store.query(q, 5, {"type": ["faq", "story"]})) == 3
    assert store.query(q, 5, {"type": "story", "founder_stage": "early"}) == []


def test_upsert_is_idempotent_and_delete_by_source(store: VectorStore) -> None:
    _fill(store)
    _fill(store)
    assert store.count() == 3
    store.delete_by_source("faq/a.md")
    assert store.count() == 1


def test_reset_and_empty_query(store: VectorStore) -> None:
    _fill(store)
    store.reset()
    assert store.count() == 0
    assert store.query(EMB.embed(["x"])[0], top_k=3) == []


def test_qdrant_point_ids_are_stable_uuids() -> None:
    assert point_id("faq/a.md#0") == point_id("faq/a.md#0") != point_id("faq/a.md#1")


def test_chroma_where_translation() -> None:
    assert to_chroma_where(None) is None
    assert to_chroma_where({"type": "faq"}) == {"type": {"$eq": "faq"}}
    assert to_chroma_where({"type": ["a", "b"], "x": 1}) == {
        "$and": [{"type": {"$in": ["a", "b"]}}, {"x": {"$eq": 1}}]
    }
