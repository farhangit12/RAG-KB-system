"""Helpers shared by loaders: folder-based type inference and source paths."""

from __future__ import annotations

from pathlib import Path

FOLDER_TYPES: dict[str, str] = {
    "stories": "story",
    "frameworks": "framework",
    "case-studies": "case_study",
    "faq": "faq",
    "insights": "insight",
    "datasets": "dataset",
    "schemes": "scheme",
    "market-reports": "market_report",
    "uploads": "upload",
}


def source_of(path: Path, root: Path) -> str:
    """Path relative to ``root`` with forward slashes (the chunk id prefix)."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def infer_type(path: Path, root: Path) -> str | None:
    """Type from the first folder under ``root`` (e.g. ``content/faq/x.md`` -> ``faq``)."""
    parts = Path(source_of(path, root)).parts
    return FOLDER_TYPES.get(parts[0]) if len(parts) > 1 else None


def page_marker(page: int) -> str:
    """Marker line the chunker reads to know which page text came from."""
    return f"<!-- page: {page} -->"
