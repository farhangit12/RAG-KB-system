"""Ports: small interfaces for every external dependency.

Feature code depends only on these Protocols and data types, never on a concrete
library. Concrete adapters live in ``app/adapters`` and are chosen in config.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
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
    """One loaded source file: its text plus metadata (from frontmatter or inferred).

    ``text`` is markdown. Loaders for PDF and DOCX add ``<!-- page: N -->`` lines so chunks
    can cite page numbers.
    """

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


@runtime_checkable
class KeywordSearch(Protocol):
    """Optional extra for a VectorStore: exact-word search (scheme names, company names)."""

    def keyword_query(
        self, text: str, top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Return up to ``top_k`` chunks containing the words of ``text``, best first."""
        ...


@runtime_checkable
class Exportable(Protocol):
    """Optional extra for a VectorStore: dump and reload everything (backups)."""

    def export_items(self) -> Iterator[tuple[Chunk, list[float]]]:
        """Yield every stored chunk with its vector."""
        ...


@runtime_checkable
class Reranker(Protocol):
    """Scores how well each text answers a question (a cross-encoder)."""

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        """Return one score in [0, 1] per text, same order. Higher is better."""
        ...


@runtime_checkable
class TokenCounter(Protocol):
    """Counts tokens the way the embedding model sees them."""

    def count(self, text: str) -> int:
        """Return the number of tokens in ``text``."""
        ...


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


def batched(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    """Split ``items`` into lists of at most ``size`` (used for embedding batches)."""
    for i in range(0, len(items), size):
        yield items[i : i + size]
