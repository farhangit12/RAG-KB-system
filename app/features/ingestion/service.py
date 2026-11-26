"""Public entry point for ingestion: ``ingest(container)``."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.core.container import Container
from app.core.logging import get_logger
from app.core.ports import Chunk, Document, MetadataValue
from app.features.ingestion.chunker import chunk_markdown
from app.features.ingestion.models import IngestReport

log = get_logger(__name__)

__all__ = ["IngestReport", "build_chunks", "discover_files", "ingest"]


def discover_files(root: Path, extensions: Sequence[str]) -> list[Path]:
    """All content files under ``root`` with a supported extension, sorted."""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def _scalar_metadata(meta: dict[str, object]) -> dict[str, MetadataValue]:
    return {k: v for k, v in meta.items() if isinstance(v, str | int | float | bool)}


def build_chunks(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Chunk one document; ids are ``{source}#{index}``."""
    base = _scalar_metadata(doc.metadata) | {"source": doc.source}
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


def ingest(container: Container) -> IngestReport:
    """Load every content file, re-chunk, embed and store it. Internal files are skipped."""
    s = container.settings
    report = IngestReport()
    for path in discover_files(s.content_dir, container.loader.extensions):
        for doc in container.loader.load(path, s.content_dir):
            container.vector_store.delete_by_source(doc.source)
            if doc.metadata.get("visibility") == "internal":
                report.skipped_internal.append(doc.source)
                continue
            chunks = build_chunks(doc, s.chunk_size, s.chunk_overlap)
            _embed_and_store(container, chunks)
            report.added.append(doc.source)
            report.chunks_written += len(chunks)
    log.info("ingest_done", extra={"files": len(report.added), "chunks": report.chunks_written})
    return report
