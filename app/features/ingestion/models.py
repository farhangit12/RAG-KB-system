"""Data types for the ingestion slice."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileResult:
    """What happened to one file."""

    source: str
    status: str            # indexed | unchanged | internal | removed | failed
    chunks: int = 0
    error: str | None = None


@dataclass
class IngestReport:
    """Summary of one ingestion run."""

    results: list[FileResult] = field(default_factory=list)

    def count(self, status: str) -> int:
        """Number of files with ``status``."""
        return sum(1 for r in self.results if r.status == status)

    @property
    def chunks(self) -> int:
        """Chunks written in this run."""
        return sum(r.chunks for r in self.results)

    @property
    def failed(self) -> list[FileResult]:
        """Files that could not be ingested."""
        return [r for r in self.results if r.status == "failed"]
