"""Repository port for feedback. Only this feature uses it, so it lives here."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.features.feedback.models import FeedbackRecord


@runtime_checkable
class FeedbackRepository(Protocol):
    """Stores and lists feedback records."""

    def add(self, record: FeedbackRecord) -> int:
        """Save ``record`` and return its new id."""
        ...

    def recent(self, limit: int = 20) -> list[FeedbackRecord]:
        """Newest records first."""
        ...
