"""Public entry point for ingestion: ``ingest(container)``.

Incremental: unchanged files (same hash) are skipped, changed files are re-embedded,
files that disappeared have their chunks deleted. Internal files are never indexed.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.core.container import Container
from app.core.logging import get_logger
from app.core.ports import Chunk, Document
from app.features.ingestion.chunker import chunk_markdown
from app.features.ingestion.manifest import (
    Manifest,
    ManifestEntry,
    file_hash,
    fingerprint,
    load_manifest,
    manifest_path,
    save_manifest,
)
from app.features.ingestion.metadata import flatten_metadata
from app.features.ingestion.models import IngestReport

log = get_logger(__name__)

__all__ = ["IngestReport", "build_chunks", "discover_files", "ingest"]


def discover_files(root: Path, extensions: Sequence[str]) -> list[Path]:
    """All content files under ``root`` with a supported extension, sorted."""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def build_chunks(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Chunk one document; ids are ``{source}#{index}``, metadata is flattened."""
    base = flatten_metadata(doc.metadata) | {"source": doc.source}
    return [
        Chunk(
            id=f"{doc.source}#{i}",
            source=doc.source,
            text=piece.text,
            metadata=base | {"heading": piece.heading, "chunk_index": i},
        )
        for i, piece in enumerate(chunk_markdown(doc.text, size, overlap))
    ]


def _embed_and_store(container: Container, chunks: list[Chunk]) -> None:
    batch = container.settings.embed_batch_size
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        vectors = container.embedder.embed([c.text for c in part])
        container.vector_store.upsert(part, vectors)


def _needs_rebuild(container: Container, manifest: Manifest, force: bool) -> bool:
    if force or manifest.fingerprint != fingerprint(container.settings):
        return True
    indexed = any(e.chunks for e in manifest.files.values())
    return indexed and container.vector_store.count() == 0  # index was wiped


def _index_file(container: Container, path: Path, report: IngestReport) -> ManifestEntry:
    s = container.settings
    entry = ManifestEntry(hash=file_hash(path), chunks=0)
    for doc in container.loader.load(path, s.content_dir):
        container.vector_store.delete_by_source(doc.source)
        entry.sources.append(doc.source)
        if doc.metadata.get("visibility") == "internal":
            entry.internal = True
            report.skipped_internal.append(doc.source)
            continue
        chunks = build_chunks(doc, s.chunk_size, s.chunk_overlap)
        _embed_and_store(container, chunks)
        entry.chunks += len(chunks)
    return entry


def ingest(container: Container, rebuild: bool = False) -> IngestReport:
    """Bring the index in line with the content folder, doing as little work as possible."""
    s = container.settings
    path = manifest_path(s)
    manifest = load_manifest(path)
    report = IngestReport()

    if _needs_rebuild(container, manifest, rebuild):
        container.vector_store.reset()
        manifest = Manifest(fingerprint=fingerprint(s))
        report.rebuilt = True

    seen: set[str] = set()
    for file in discover_files(s.content_dir, container.loader.extensions):
        rel = file.relative_to(s.content_dir).as_posix()
        seen.add(rel)
        old = manifest.files.get(rel)
        if old and old.hash == file_hash(file):
            report.unchanged.append(rel)
            continue
        for source in old.sources if old else []:
            container.vector_store.delete_by_source(source)
        entry = _index_file(container, file, report)
        manifest.files[rel] = entry
        (report.updated if old else report.added).append(rel)
        report.chunks_written += entry.chunks

    for rel in sorted(set(manifest.files) - seen):
        for source in manifest.files.pop(rel).sources:
            container.vector_store.delete_by_source(source)
        report.removed.append(rel)

    save_manifest(path, manifest)
    log.info(
        "ingest_done",
        extra={
            "added": len(report.added),
            "updated": len(report.updated),
            "unchanged": len(report.unchanged),
            "removed": len(report.removed),
            "chunks": report.chunks_written,
            "rebuilt": report.rebuilt,
        },
    )
    return report
