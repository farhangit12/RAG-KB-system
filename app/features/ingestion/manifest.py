"""Incremental ingestion: remember each file's hash so unchanged files are skipped.

Stored as ``DATA_DIR/manifest.json``: ``{source: {"sha256": ..., "chunks": n, "origin": ...}}``.
``origin`` is ``content`` for files under CONTENT_DIR and ``upload`` for founder uploads, so
a content re-scan only removes content files that disappeared.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Manifest:
    """A small JSON file; written atomically."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: dict[str, dict[str, Any]] = {}
        if path.exists():
            self.entries = json.loads(path.read_text(encoding="utf-8"))

    def unchanged(self, source: str, sha256: str) -> bool:
        """True if ``source`` was indexed before with the same content hash."""
        return self.entries.get(source, {}).get("sha256") == sha256

    def find_hash(self, sha256: str, exclude: str, origin: str, prefix: str = "") -> str | None:
        """Another source from the same origin (and folder prefix) with identical bytes."""
        for source, entry in self.entries.items():
            if (
                source != exclude
                and entry.get("sha256") == sha256
                and entry.get("origin") == origin
                and source.startswith(prefix)
            ):
                return source
        return None

    def record(self, source: str, sha256: str, chunks: int, origin: str) -> None:
        """Remember a successful ingest."""
        self.entries[source] = {"sha256": sha256, "chunks": chunks, "origin": origin}

    def forget(self, source: str) -> None:
        """Drop a source (deleted or removed)."""
        self.entries.pop(source, None)

    def sources(self, origin: str) -> set[str]:
        """All sources from one origin."""
        return {s for s, e in self.entries.items() if e.get("origin") == origin}

    def save(self) -> None:
        """Write to disk (via a temp file, so a crash never leaves half a file)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.entries, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
