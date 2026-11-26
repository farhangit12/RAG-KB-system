from __future__ import annotations

from pathlib import Path

from app.core.container import Container
from app.features.ingestion.service import ingest


def test_ingests_all_sample_files(tmp_container: Container) -> None:
    report = ingest(tmp_container)
    assert sorted(report.added) == [
        "case-studies/bhumi.md",
        "faq/direction-call.md",
        "frameworks/disha-path.md",
        "stories/sara-and-anshuman.md",
    ]
    assert tmp_container.vector_store.count() == report.chunks_written > 0


def test_chunk_ids_are_stable_and_carry_metadata(tmp_container: Container) -> None:
    ingest(tmp_container)
    vec = tmp_container.embedder.embed(["talk to ten real people"])[0]
    hits = tmp_container.vector_store.query(vec, top_k=50)
    ids = {h.chunk.id for h in hits}
    assert "frameworks/disha-path.md#0" in ids
    meta = next(h.chunk.metadata for h in hits if h.chunk.id == "frameworks/disha-path.md#0")
    assert meta["title"] == "The Disha Path"
    assert meta["type"] == "framework"
    assert meta["source"] == "frameworks/disha-path.md"


def test_internal_files_are_never_indexed(tmp_container: Container, content_copy: Path) -> None:
    secret = content_copy / "faq" / "pricing-notes.md"
    secret.write_text(
        '---\ntitle: "Internal pricing"\ntype: faq\nvisibility: internal\n---\nSecret notes.',
        encoding="utf-8",
    )
    report = ingest(tmp_container)
    assert report.skipped_internal == ["faq/pricing-notes.md"]
    vec = tmp_container.embedder.embed(["secret notes pricing"])[0]
    hits = tmp_container.vector_store.query(vec, top_k=100)
    assert all(h.chunk.source != "faq/pricing-notes.md" for h in hits)


def test_reingest_does_not_duplicate(tmp_container: Container) -> None:
    first = ingest(tmp_container)
    ingest(tmp_container)
    assert tmp_container.vector_store.count() == first.chunks_written
