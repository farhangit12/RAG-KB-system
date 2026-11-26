"""Data types for retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.metadata_keys import flag_key
from app.core.ports import MetadataValue


@dataclass(frozen=True)
class UserContext:
    """What we know about the asker. Used to tailor and (Slice 4) rank results."""

    stage: str | None = None
    sector: str | None = None


@dataclass(frozen=True)
class QueryFilters:
    """Optional metadata filters. Lists mean "any of"."""

    type: list[str] = field(default_factory=list)
    stage: list[str] = field(default_factory=list)
    sector: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    def to_filter(self) -> dict[str, MetadataValue | list[MetadataValue]]:
        """Translate to the neutral ``Filter`` used by every VectorStore."""
        out: dict[str, MetadataValue | list[MetadataValue]] = {}
        for key, values in (
            ("type", self.type),
            ("founder_stage", self.stage),
            ("sector", self.sector),
        ):
            if values:
                out[key] = values[0] if len(values) == 1 else list(values)
        for name, values in (("people", self.people), ("topics", self.topics)):
            for v in values:
                out[flag_key(name, v)] = True
        return out
