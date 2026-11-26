"""HTTP route: ``POST /feedback``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.api_deps import ContainerDep, rate_limit
from app.core.config import Settings
from app.features.feedback import service
from app.features.feedback.models import Rating
from app.features.feedback.ports import FeedbackRepository

router = APIRouter(tags=["feedback"], dependencies=[Depends(rate_limit)])


class FeedbackIn(BaseModel):
    """Body of ``POST /feedback``. Length limits come from settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)
    rating: Rating
    comment: str | None = None


class FeedbackOut(BaseModel):
    """Body returned by ``POST /feedback``."""

    id: int


def get_repository(request: Request) -> FeedbackRepository:
    """The repository created in ``create_app``."""
    return request.app.state.feedback_repo


RepoDep = Annotated[FeedbackRepository, Depends(get_repository)]


def check_limits(body: FeedbackIn, s: Settings) -> None:
    """Reject over-long inputs with 422."""
    checks = [
        (len(body.question) > s.max_question_chars, f"question (max {s.max_question_chars})"),
        (len(body.answer) > s.max_answer_chars, f"answer (max {s.max_answer_chars})"),
        (len(body.comment or "") > s.max_comment_chars, f"comment (max {s.max_comment_chars})"),
        (len(body.sources) > s.max_feedback_sources, f"sources (max {s.max_feedback_sources})"),
        (any(len(x) > 300 for x in body.sources), "source path (max 300)"),
    ]
    for failed, what in checks:
        if failed:
            raise HTTPException(422, f"Too long: {what}.")


@router.post("/feedback", status_code=201, response_model=FeedbackOut)
def post_feedback(body: FeedbackIn, container: ContainerDep, repo: RepoDep) -> FeedbackOut:
    """Save a thumbs up/down (and optional comment) for an answer."""
    check_limits(body, container.settings)
    new_id = service.submit(
        repo, body.question, body.answer, body.rating, body.sources, body.comment
    )
    return FeedbackOut(id=new_id)
