"""Answering: retrieve -> pack -> prompt -> generate -> check citations.

If retrieval finds nothing above the rerank threshold, a fixed "not in the knowledge base"
answer is returned WITHOUT calling the LLM, which also saves free-plan quota.
"""

from __future__ import annotations

import re

from app.core.container import Container
from app.core.logging import get_logger
from app.features.chat.models import AnswerResult, Source
from app.features.chat.packing import pack
from app.features.chat.prompts import NOT_FOUND, SYSTEM, build_prompt
from app.features.retrieval import service as retrieval
from app.features.retrieval.service import BusinessProfile

log = get_logger(__name__)

_LABEL = re.compile(r"\[(S\d+)\]")


def check_citations(answer: str, sources: list[Source]) -> tuple[str, list[str], list[str]]:
    """Remove labels that point at no packed source. Returns (answer, cited, invalid)."""
    valid = {s.label for s in sources}
    cited: list[str] = []
    invalid: list[str] = []
    for label in _LABEL.findall(answer):
        target = cited if label in valid else invalid
        if label not in target:
            target.append(label)
    for label in invalid:
        answer = answer.replace(f"[{label}]", "")
    return answer, cited, invalid


def _fit(container: Container, question: str, sources: list[Source],
         profile: BusinessProfile | None) -> tuple[str, list[Source], int]:
    """Drop the lowest-ranked sources until the whole call fits MAX_INPUT_TOKENS."""
    count = container.tokenizer.count
    limit = container.settings.max_input_tokens
    while True:
        prompt = build_prompt(question, sources, profile)
        tokens = count(SYSTEM) + count(prompt)
        if tokens <= limit or len(sources) <= 1:
            return prompt, sources, tokens
        sources = sources[:-1]


def answer(
    container: Container, question: str, profile: BusinessProfile | None = None
) -> AnswerResult:
    """Answer ``question`` from the knowledge base, with checked citations."""
    question = question.strip()
    if not question:
        raise ValueError("question is empty")
    result = retrieval.retrieve(container, question, profile)
    if not result.found:
        return AnswerResult(answer=NOT_FOUND, found=False)

    packed = pack(
        [(c.chunk, c.rerank or 0.0) for c in result.kept],
        container.tokenizer,
        container.settings.pack_token_budget,
    )
    prompt, packed, tokens = _fit(container, question, packed, profile)
    raw = container.llm.generate(SYSTEM, prompt)
    text, cited, invalid = check_citations(raw, packed)
    low = not cited
    log.info("answered", extra={"sources": len(packed), "cited": len(cited),
                                "invalid": len(invalid), "prompt_tokens": tokens})
    return AnswerResult(
        answer=text.strip(), found=True, sources=packed, cited=cited,
        invalid_citations=invalid, low_confidence=low, prompt_tokens=tokens,
    )
