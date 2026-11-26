"""Incremental ingestion: only changed files are re-embedded, removed files are deleted."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.core.container import Container
from app.features.ingestion.manifest import load_manifest, manifest_path
from app.features.ingestion.service import ingest

NEW_FILE = '---\ntitle: "New FAQ"\ntype: faq\n---\n# New FAQ\n\nA brand new answer.'


class CountingEmbedder:
    """Wraps an embedder and counts how many texts were embedded."""

    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.texts = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts += len(texts)
        return self.inner.embed(texts)  # type: ignore[attr-defined]


def _counting(container: Container) -> CountingEmbedder:
    counter = CountingEmbedder(container.embedder)
    container.__dict__["embedder"] = counter  # replace the cached adapter
    return counter


def _sources(container: Container) -> set[str]:
    vec = container.embedder.embed(["anything"])[0]
    return {h.chunk.source for h in container.vector_store.query(vec, top_k=1000)}


def test_second_run_embeds_nothing(tmp_container: Container) -> None:
    ingest(tmp_container)
    counter = _counting(tmp_container)
    report = ingest(tmp_container)
    assert counter.texts == 0
    assert len(report.unchanged) == 4
    assert not report.rebuilt


def test_only_changed_file_is_reembedded(tmp_container: Container, content_copy: Path) -> None:
    first = ingest(tmp_container)
    total = tmp_container.vector_store.count()
    faq = content_copy / "faq" / "direction-call.md"
    faq.write_text(faq.read_text(encoding="utf-8") + "\n\nOne more line.", encoding="utf-8")

    counter = _counting(tmp_container)
    report = ingest(tmp_container)
    assert report.updated == ["faq/direction-call.md"]
    assert len(report.unchanged) == 3
    assert 0 < counter.texts < first.chunks_written
    assert tmp_container.vector_store.count() == total - (total - first.chunks_written)


def test_new_and_removed_files(tmp_container: Container, content_copy: Path) -> None:
    ingest(tmp_container)
    (content_copy / "faq" / "new.md").write_text(NEW_FILE, encoding="utf-8")
    (content_copy / "case-studies" / "bhumi.md").unlink()

    report = ingest(tmp_container)
    assert report.added == ["faq/new.md"]
    assert report.removed == ["case-studies/bhumi.md"]
    sources = _sources(tmp_container)
    assert "faq/new.md" in sources
    assert "case-studies/bhumi.md" not in sources
    assert "case-studies/bhumi.md" not in load_manifest(manifest_path(tmp_container.settings)).files


def test_file_turned_internal_is_removed(tmp_container: Container, content_copy: Path) -> None:
    ingest(tmp_container)
    bhumi = content_copy / "case-studies" / "bhumi.md"
    bhumi.write_text(
        bhumi.read_text(encoding="utf-8").replace("visibility: public", "visibility: internal"),
        encoding="utf-8",
    )
    report = ingest(tmp_container)
    assert report.skipped_internal == ["case-studies/bhumi.md"]
    assert "case-studies/bhumi.md" not in _sources(tmp_container)


def test_settings_change_triggers_rebuild(tmp_container: Container) -> None:
    ingest(tmp_container)
    changed = Container(tmp_container.settings.model_copy(update={"chunk_size": 400}))
    changed.__dict__["vector_store"] = tmp_container.vector_store
    report = ingest(changed)
    assert report.rebuilt
    assert len(report.added) == 4


def test_wiped_index_triggers_rebuild(tmp_container: Container) -> None:
    ingest(tmp_container)
    tmp_container.vector_store.reset()
    report = ingest(tmp_container)
    assert report.rebuilt
    assert tmp_container.vector_store.count() > 0


def test_rebuild_flag(tmp_container: Container) -> None:
    ingest(tmp_container)
    report = ingest(tmp_container, rebuild=True)
    assert report.rebuilt
    assert len(report.added) == 4
