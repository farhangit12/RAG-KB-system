"""HTTP endpoint for asking a question."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.container import Container
from app.features.chat import service
from app.features.retrieval.service import BusinessProfile
from app.web import get_container

router = APIRouter(tags=["chat"])


class ProfileIn(BaseModel):
    business_id: str
    sector: str | None = None
    founder_stage: str | None = None
    location: str | None = None
    business_model: str | None = None
    target_audience: str | None = None
    summary: str | None = Field(default=None, max_length=2000)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    profile: ProfileIn | None = None


@router.post("/ask")
def ask(body: AskIn, container: Container = Depends(get_container)) -> dict:
    """Answer a founder's question from the knowledge base, with sources."""
    profile = BusinessProfile(**body.profile.model_dump()) if body.profile else None
    try:
        result = service.answer(container, body.question, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return asdict(result)
