from __future__ import annotations

from pathlib import Path

from app.core.container import Container
from app.features.ingestion import service
from tests.conftest import write

FAQ = """---
title: "Seed funding basics"
type: faq
people: [Sara]
founder_stage: idea
sector: general
topics: [funding]
date: 2026-05
visibility: public
---

# Seed funding

Seed funding is the first outside money a startup raises.
"""


def test_ingest_is_incremental_and_removes_deleted_files(kb_container: Container) -> None:
    root = kb_container.settings.content_dir
    write(root / "faq" / "seed.md", FAQ)
    pricing = FAQ.replace("Seed funding", "Pricing").replace("faq", "framework")
    write(root / "frameworks" / "pricing.md", pricing)

    first = service.ingest_content(kb_container)
    assert first.count("indexed") == 2
    assert kb_container.vector_store.count() == 2

    second = service.ingest_content(kb_container)
    assert second.count("unchanged") == 2

    (root / "faq" / "seed.md").unlink()
    third = service.ingest_content(kb_container)
    assert third.count("removed") == 1
    assert kb_container.vector_store.count() == 1


def test_internal_files_are_never_indexed(kb_container: Container) -> None:
    write(kb_container.settings.content_dir / "faq" / "notes.md",
          FAQ.replace("visibility: public", "visibility: internal"))
    report = service.ingest_content(kb_container)
    assert report.count("internal") == 1
    assert kb_container.vector_store.count() == 0


def test_duplicates_and_bad_metadata_are_reported(kb_container: Container) -> None:
    root = kb_container.settings.content_dir
    write(root / "faq" / "a.md", FAQ)
    write(root / "faq" / "b.md", FAQ)
    write(root / "schemes" / "old.txt", "Some scheme text.")
    write(root / "schemes" / "old.txt.meta.yaml", "valid_until: tomorrow\n")
    report = service.ingest_content(kb_container)
    assert report.count("indexed") == 1
    assert report.count("duplicate") == 1
    assert [r.source for r in report.failed] == ["schemes/old.txt"]


def test_chunk_metadata_is_scalar_and_complete(kb_container: Container) -> None:
    write(kb_container.settings.content_dir / "faq" / "seed.md", FAQ)
    service.ingest_content(kb_container)
    [(chunk, vector)] = list(kb_container.vector_store.export_items())
    assert chunk.id == "faq/seed.md#0"
    assert all(isinstance(v, str | int | float | bool) for v in chunk.metadata.values())
    for key in ("title", "type", "visibility", "chunk_index", "token_count", "content_sha256",
                "source_sha256", "embed_model"):
        assert key in chunk.metadata
    assert chunk.metadata["people"] == "Sara"


def test_csv_and_txt_with_sidecar(kb_container: Container) -> None:
    root = kb_container.settings.content_dir
    rows = "\n".join(f"City{i},{i * 10}" for i in range(5))
    write(root / "datasets" / "prices.csv", "city,price\n" + rows)
    write(root / "datasets" / "prices.csv.meta.yaml", "title: Chai prices\nsector: foodtech\n")
    report = service.ingest_content(kb_container)
    assert report.count("indexed") == 1
    [(chunk, _)] = list(kb_container.vector_store.export_items())
    assert chunk.metadata["type"] == "dataset"
    assert chunk.metadata["title"] == "Chai prices"
    assert "| city | price |" in chunk.text


def test_upload_is_private_to_its_business(kb_container: Container) -> None:
    folder = kb_container.settings.data_dir / "uploads" / "biz-1"
    path = write(Path(folder) / "pnl.txt", "Monthly revenue was 4 lakh in March.")
    result = service.ingest_upload(kb_container, path, "biz-1", title="P&L")
    assert result.status == "indexed"
    [(chunk, _)] = list(kb_container.vector_store.export_items())
    assert chunk.metadata["visibility"] == "private"
    assert chunk.metadata["business_id"] == "biz-1"
    service.delete_source(kb_container, chunk.source)
    assert kb_container.vector_store.count() == 0
