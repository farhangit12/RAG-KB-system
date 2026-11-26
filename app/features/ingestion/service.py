"""Ingestion: file -> validate -> load -> clean -> chunk -> metadata -> embed -> store.

Public entry points (other features call only these):
- ``ingest_content(container)``: index everything under CONTENT_DIR, incrementally.
- ``ingest_upload(container, path, business_id, ...)``: index one founder's private file.
- ``delete_source(container, source)``: remove a file's chunks and vectors.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.core.container import Container
from app.core.logging import get_logger
from app.core.ports import Chunk, MetadataValue, batched
from app.features.ingestion.chunking import chunk_markdown
from app.features.ingestion.cleaning import clean_markdown
from app.features.ingestion.manifest import Manifest
from app.features.ingestion.metadata import MetadataError, normalise
from app.features.ingestion.models import FileResult, IngestReport

log = get_logger(__name__)

UPLOADS_DIR = "uploads"


def _manifest(container: Container) -> Manifest:
    return Manifest(container.settings.data_dir / "manifest.json")


def _file_hash(path: Path) -> str:
    """Hash of the file plus its sidecar metadata, so a metadata edit also re-indexes."""
    h = hashlib.sha256(path.read_bytes())
    side = path.with_name(path.name + ".meta.yaml")
    if side.exists():
        h.update(side.read_bytes())
    return h.hexdigest()


def _build_chunks(
    container: Container, source: str, text: str, meta: dict[str, MetadataValue], file_sha: str
) -> list[Chunk]:
    s = container.settings
    cleaned = clean_markdown(text)
    pieces = chunk_markdown(cleaned, container.tokenizer, s.chunk_size, s.chunk_overlap)
    chunks = []
    for i, p in enumerate(pieces):
        extra: dict[str, Any] = {
            "chunk_index": i,
            "token_count": p.tokens,
            "page_start": p.page_start,
            "page_end": p.page_end,
            "section": p.section,
            "content_sha256": hashlib.sha256(p.text.encode()).hexdigest(),
            "source_sha256": file_sha,
            "embed_model": s.embed_model if s.embedder != "fake" else "fake",
        }
        metadata = {**meta, **{k: v for k, v in extra.items() if v is not None}}
        chunks.append(Chunk(id=f"{source}#{i}", source=source, text=p.text, metadata=metadata))
    return chunks


def _index_file(
    container: Container,
    path: Path,
    root: Path,
    origin: str,
    manifest: Manifest,
    extra_meta: dict[str, Any] | None = None,
) -> FileResult:
    s = container.settings
    source = path.resolve().relative_to(root.resolve()).as_posix()
    try:
        if path.stat().st_size > s.max_file_mb * 1024 * 1024:
            raise MetadataError(f"file is over the {s.max_file_mb} MB limit")
        file_sha = _file_hash(path)
        if manifest.unchanged(source, file_sha):
            return FileResult(source, "unchanged")
        prefix = source.rsplit("/", 1)[0] + "/" if origin == "upload" else ""
        dup = manifest.find_hash(file_sha, exclude=source, origin=origin, prefix=prefix)
        if dup:
            return FileResult(source, "duplicate", error=f"same content as {dup}")

        docs = container.loader.load(path, root)
        chunks: list[Chunk] = []
        for doc in docs:
            meta = normalise({**doc.metadata, **(extra_meta or {}), "source": doc.source})
            if meta["visibility"] == "internal":
                container.vector_store.delete_by_source(source)
                manifest.record(source, file_sha, 0, origin)
                return FileResult(source, "internal")
            built = _build_chunks(container, doc.source, doc.text, meta, file_sha)
            offset = len(chunks)
            chunks.extend(
                Chunk(id=f"{c.source}#{offset + j}", source=c.source, text=c.text,
                      metadata={**c.metadata, "chunk_index": offset + j})
                for j, c in enumerate(built)
            )
        if not chunks:
            raise MetadataError("no text could be extracted")

        vectors: list[list[float]] = []
        for batch in batched([c.text for c in chunks], s.embed_batch_size):
            vectors.extend(container.embedder.embed(batch))
        container.vector_store.delete_by_source(source)
        container.vector_store.upsert(chunks, vectors)
        manifest.record(source, file_sha, len(chunks), origin)
        log.info("indexed", extra={"source": source, "chunks": len(chunks)})
        return FileResult(source, "indexed", chunks=len(chunks))
    except Exception as exc:  # one bad file must not stop the run
        log.warning("ingest failed", extra={"source": source, "error": str(exc)})
        return FileResult(source, "failed", error=str(exc))


def ingest_content(container: Container) -> IngestReport:
    """Index every supported file under CONTENT_DIR; skip unchanged; drop deleted files."""
    root = container.settings.content_dir
    manifest = _manifest(container)
    report = IngestReport()
    exts = set(container.loader.extensions)
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in exts or path.name.startswith("."):
            continue
        result = _index_file(container, path, root, "content", manifest)
        seen.add(result.source)
        report.results.append(result)
    for gone in sorted(manifest.sources("content") - seen):
        container.vector_store.delete_by_source(gone)
        manifest.forget(gone)
        report.results.append(FileResult(gone, "removed"))
    manifest.save()
    return report


def ingest_upload(
    container: Container,
    path: Path,
    business_id: str,
    title: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> FileResult:
    """Index one founder's private file. ``path`` must be under DATA_DIR/uploads/<business_id>/."""
    data_dir = container.settings.data_dir
    expected = (data_dir / UPLOADS_DIR / business_id).resolve()
    if expected not in path.resolve().parents:
        raise ValueError(f"upload must be saved under {expected}")
    manifest = _manifest(container)
    meta = {"visibility": "private", "business_id": business_id, "type": "upload",
            **(extra_meta or {})}
    if title:
        meta["title"] = title
    result = _index_file(container, path, data_dir, "upload", manifest, meta)
    manifest.save()
    return result


def delete_source(container: Container, source: str) -> None:
    """Remove a file's chunks and vectors from the store and the manifest."""
    container.vector_store.delete_by_source(source)
    manifest = _manifest(container)
    manifest.forget(source)
    manifest.save()
