"""Public entry points for chat: ``answer`` and ``stream_answer``."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from app.core.container import Container
from app.core.ports import ScoredChunk
from app.features.chat.models import Answer, SourceRef
from app.features.chat.prompts import SYSTEM_PROMPT, build_user_prompt
from app.features.retrieval.service import QueryFilters, retrieve

__all__ = ["Answer", "SourceRef", "answer", "stream_answer", "to_source_refs"]


def to_source_refs(chunks: Sequence[ScoredChunk]) -> list[SourceRef]:
    """One SourceRef per file, ordered by best score."""
    best: dict[str, SourceRef] = {}
    for sc in chunks:
        meta = sc.chunk.metadata
        ref = SourceRef(
            title=str(meta.get("title", sc.chunk.source)),
            source=sc.chunk.source,
            type=str(meta.get("type", "")),
            score=round(sc.score, 4),
        )
        if sc.chunk.source not in best or ref.score > best[sc.chunk.source].score:
            best[sc.chunk.source] = ref
    return sorted(best.values(), key=lambda r: r.score, reverse=True)


def _prepare(
    container: Container, question: str, filters: QueryFilters | None
) -> tuple[str, list[ScoredChunk]]:
    chunks = retrieve(container, question, filters=filters)
    return build_user_prompt(question, chunks), chunks


def answer(container: Container, question: str, filters: QueryFilters | None = None) -> Answer:
    """Retrieve sources and return a grounded, cited answer."""
    prompt, chunks = _prepare(container, question, filters)
    text = container.llm.generate(SYSTEM_PROMPT, prompt)
    return Answer(text=text, sources=to_source_refs(chunks))


def stream_answer(
    container: Container, question: str, filters: QueryFilters | None = None
) -> tuple[list[SourceRef], Iterator[str]]:
    """Like ``answer`` but returns the sources first and the text as a stream."""
    prompt, chunks = _prepare(container, question, filters)
    return to_source_refs(chunks), container.llm.stream(SYSTEM_PROMPT, prompt)
