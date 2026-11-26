"""HTTP request/response shapes for the chat API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.features.chat.models import SourceRef
from app.features.chat.service import UserContext


class UserContextIn(BaseModel):
    """Optional info about the asker."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stage: Literal["idea", "early", "traction"] | None = None
    sector: str | None = None

    def to_domain(self) -> UserContext:
        """Convert to the retrieval feature's type."""
        return UserContext(stage=self.stage, sector=self.sector or None)


class ChatRequest(BaseModel):
    """Body of ``POST /chat`` and ``POST /chat/stream``. Length limits come from settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1)
    user_context: UserContextIn | None = None


class SourceOut(BaseModel):
    """One cited source."""

    title: str
    source: str
    type: str
    score: float

    @classmethod
    def from_ref(cls, ref: SourceRef) -> SourceOut:
        """Build from the service's SourceRef."""
        return cls(title=ref.title, source=ref.source, type=ref.type, score=ref.score)


class ChatResponse(BaseModel):
    """Body returned by ``POST /chat``."""

    answer: str
    sources: list[SourceOut]
