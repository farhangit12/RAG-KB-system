from __future__ import annotations

import math

from app.adapters.embedders.fake import FakeEmbedder
from app.adapters.llms.fake import FakeLLM
from app.adapters.vectorstores.memory_store import MemoryVectorStore
from app.core.ports import Chunk


def _chunk(cid: str, source: str, text: str, **meta: str) -> Chunk:
    return Chunk(id=cid, source=source, text=text, metadata=dict(meta))


def test_fake_embedder_is_deterministic_and_normalised() -> None:
    emb = FakeEmbedder()
    a, b = emb.embed(["talk to ten real people", "talk to ten real people"])
    assert a == b
    assert math.isclose(sum(x * x for x in a), 1.0)


def test_memory_store_query_filter_and_delete() -> None:
    emb = FakeEmbedder()
    store = MemoryVectorStore()
    chunks = [
        _chunk("faq/a.md#0", "faq/a.md", "book a direction call", type="faq"),
        _chunk("stories/b.md#0", "stories/b.md", "waterpro failed", type="story"),
    ]
    store.upsert(chunks, emb.embed([c.text for c in chunks]))
    assert store.count() == 2

    [top] = store.query(emb.embed(["direction call"])[0], top_k=1)
    assert top.chunk.id == "faq/a.md#0"

    only_stories = store.query(emb.embed(["direction call"])[0], top_k=5, where={"type": "story"})
    assert [s.chunk.id for s in only_stories] == ["stories/b.md#0"]

    either = store.query(emb.embed(["x"])[0], top_k=5, where={"type": ["faq", "story"]})
    assert len(either) == 2

    store.delete_by_source("faq/a.md")
    assert store.count() == 1


def test_memory_store_upsert_replaces_same_id() -> None:
    emb = FakeEmbedder()
    store = MemoryVectorStore()
    store.upsert([_chunk("x#0", "x", "old")], emb.embed(["old"]))
    store.upsert([_chunk("x#0", "x", "new")], emb.embed(["new"]))
    [hit] = store.query(emb.embed(["new"])[0], top_k=1)
    assert store.count() == 1
    assert hit.chunk.text == "new"


def test_fake_llm_records_calls_and_streams() -> None:
    llm = FakeLLM(reply="hello there founder")
    assert "".join(llm.stream("sys", "q")) == "hello there founder"
    assert llm.calls == [("sys", "q")]
