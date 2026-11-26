"""HTTP routes: ``POST /chat`` (JSON) and ``POST /chat/stream`` (server-sent events)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.api_deps import ContainerDep, rate_limit
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.ports import LLMError
from app.features.chat import service
from app.features.chat.schemas import ChatRequest, ChatResponse, SourceOut

log = get_logger(__name__)
router = APIRouter(tags=["chat"], dependencies=[Depends(rate_limit)])

UNAVAILABLE = "The assistant is unavailable right now. Please try again in a moment."


def check_limits(req: ChatRequest, settings: Settings) -> None:
    """Reject over-long inputs with 422 (limits are configurable)."""
    if len(req.question) > settings.max_question_chars:
        raise HTTPException(
            422, f"Question is too long (max {settings.max_question_chars} characters)."
        )
    sector = req.user_context.sector if req.user_context else None
    if sector and len(sector) > settings.max_sector_chars:
        raise HTTPException(422, f"Sector is too long (max {settings.max_sector_chars}).")


def _context(req: ChatRequest) -> service.UserContext | None:
    return req.user_context.to_domain() if req.user_context else None


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, container: ContainerDep) -> ChatResponse:
    """Answer a question with citations."""
    check_limits(req, container.settings)
    try:
        result = service.answer(container, req.question, context=_context(req))
    except LLMError as e:
        raise HTTPException(502, UNAVAILABLE) from e
    return ChatResponse(answer=result.text, sources=[SourceOut.from_ref(s) for s in result.sources])


def sse(event: str, data: dict[str, Any]) -> str:
    """Format one server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def chat_stream(req: ChatRequest, container: ContainerDep) -> Any:
    """Stream the answer. Events: ``sources``, then ``token``s, then ``done`` (or ``error``)."""
    check_limits(req, container.settings)
    sources, tokens = service.stream_answer(container, req.question, context=_context(req))

    def events() -> Iterator[str]:
        yield sse("sources", {"sources": [SourceOut.from_ref(s).model_dump() for s in sources]})
        try:
            for text in tokens:
                yield sse("token", {"text": text})
        except LLMError:
            log.exception("stream_failed")
            yield sse("error", {"message": UNAVAILABLE})
            return
        yield sse("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
