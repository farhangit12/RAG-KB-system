"""Data types for ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IngestReport:
    """What one ingestion run did."""

    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped_internal: list[str] = field(default_factory=list)
    chunks_written: int = 0
    rebuilt: bool = False
