"""Backups: export every chunk with its vector to a JSONL file, and restore from one.

The Always Free Autonomous database has no backup or restore of its own, so this export is
the backup. Copy the file to Object Storage in Account 4 (for example with the free OCI
CLI: ``oci os object put --bucket-name disha-kb-backup --file <file>``). The original
files are kept too, so the KB can always be rebuilt with ``ingest`` as a last resort.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

from app.core.container import Container
from app.core.logging import get_logger
from app.core.ports import Chunk, Exportable, batched

log = get_logger(__name__)


def export_jsonl(container: Container, out_dir: Path | None = None) -> Path:
    """Write ``kb-YYYYMMDD-HHMMSS.jsonl.gz``; one line per chunk."""
    store = container.vector_store
    if not isinstance(store, Exportable):
        raise TypeError(f"{type(store).__name__} does not support export")
    out_dir = out_dir or container.settings.backup_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"kb-{stamp}.jsonl.gz"
    n = 0
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for chunk, vector in store.export_items():
            row = {"id": chunk.id, "source": chunk.source, "text": chunk.text,
                   "metadata": chunk.metadata, "embedding": vector}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    log.info("backup written", extra={"file": str(path), "chunks": n})
    return path


def restore_jsonl(container: Container, path: Path, batch_size: int = 200) -> int:
    """Load a backup file into the configured store. Returns the number of chunks."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    for batch in batched(rows, batch_size):
        chunks = [Chunk(r["id"], r["source"], r["text"], r["metadata"]) for r in batch]
        container.vector_store.upsert(chunks, [r["embedding"] for r in batch])
    log.info("backup restored", extra={"file": str(path), "chunks": len(rows)})
    return len(rows)
