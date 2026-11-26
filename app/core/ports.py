"""Ports: small interfaces for every external dependency.

Feature code depends only on these Protocols and data types, never on a concrete
library. Concrete adapters live in ``app/adapters`` and are chosen in config.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

MetadataValue = str | int | float | bool
"""Chunk metadata values must be scalars so every vector store can filter on them."""

Filter = Mapping[str, MetadataValue | Sequence[MetadataValue]]
"""Metadata filter: ``{"type": "faq"}`` means equals; ``{"type": ["faq", "story"]}`` means
"one of". All keys must match (AND). Adapters translate this to their own query syntax."""


@dataclass(frozen=True)
class Document:
    """One loaded source file: its text plus metadata (from frontmatter or inferred)."""

    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """A piece of a document that gets embedded. ``id`` is ``{source}#{index}``."""

    id: str
    source: str
    text: str
    metadata: dict[str, MetadataValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredChunk:
    """A chunk returned by a query. Higher ``score`` means more similar."""

    chunk: Chunk
    score: float


@runtime_checkable
class Embedder(Protocol):
    """Turns texts into vectors."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Stores chunks with their vectors and finds the nearest ones."""

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace chunks (matched by ``chunk.id``)."""
        ...

    def delete_by_source(self, source: str) -> None:
        """Remove every chunk that came from ``source``."""
        ...

    def query(
        self, embedding: Sequence[float], top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Return up to ``top_k`` chunks most similar to ``embedding`` matching ``where``."""
        ...

    def count(self) -> int:
        """Return the number of stored chunks."""
        ...

    def reset(self) -> None:
        """Delete everything (used when the embedder or chunking settings change)."""
        ...


class LLMError(RuntimeError):
    """The LLM could not produce an answer (network, auth, rate limit, server error)."""


@runtime_checkable
class LLM(Protocol):
    """A text generation model."""

    def generate(self, system: str, prompt: str) -> str:
        """Return the full answer for ``prompt`` under ``system`` instructions."""
        ...

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        """Yield the answer as text pieces while it is generated."""
        ...


@runtime_checkable
class DocumentLoader(Protocol):
    """Reads one file into one or more Documents."""

    extensions: tuple[str, ...]

    def load(self, path: Path, root: Path) -> list[Document]:
        """Load ``path``; ``source`` is the path relative to ``root`` (forward slashes)."""
        ...
