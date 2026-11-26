"""The manifest remembers what was indexed, so re-runs only touch changed files.

Stored as JSON in ``DATA_DIR/manifest-<collection>.json``::

    {"fingerprint": "...", "files": {"faq/a.md": {"hash": "...", "chunks": 3, ...}}}

The fingerprint captures every setting that changes the vectors (embedder, store,
chunk size...). If it changes, the whole index is rebuilt.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.core.config import Settings

CHUNKER_VERSION = "1"


@dataclass
class ManifestEntry:
    """What we know about one indexed file."""

    hash: str
    chunks: int
    sources: list[str] = field(default_factory=list)
    internal: bool = False


@dataclass
class Manifest:
    """All indexed files plus the settings fingerprint they were built with."""

    fingerprint: str = ""
    files: dict[str, ManifestEntry] = field(default_factory=dict)


def manifest_path(settings: Settings) -> Path:
    """Where the manifest for the configured collection lives."""
    return settings.data_dir / f"manifest-{settings.collection_public}.json"


def fingerprint(settings: Settings) -> str:
    """A string that changes whenever re-embedding everything is required."""
    parts = [
        settings.embedder,
        settings.vector_store,
        settings.collection_public,
        str(settings.chunk_size),
        str(settings.chunk_overlap),
        CHUNKER_VERSION,
    ]
    return "|".join(parts)


def file_hash(path: Path) -> str:
    """SHA-256 of the file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path) -> Manifest:
    """Read the manifest, or return an empty one if missing or unreadable."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        files = {k: ManifestEntry(**v) for k, v in raw.get("files", {}).items()}
        return Manifest(fingerprint=raw.get("fingerprint", ""), files=files)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return Manifest()


def save_manifest(path: Path, manifest: Manifest) -> None:
    """Write atomically: a crash never leaves a half-written manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
