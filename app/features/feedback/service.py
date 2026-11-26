"""Public entry points for feedback: ``build_repository``, ``submit``, ``recent``."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.logging import get_logger
from app.features.feedback.models import FeedbackRecord, Rating
from app.features.feedback.ports import FeedbackRepository
from app.features.feedback.sqlite_repo import SQLiteFeedbackRepository

log = get_logger(__name__)

__all__ = ["FeedbackRecord", "FeedbackRepository", "build_repository", "recent", "submit"]


def _sqlite(settings: Settings) -> FeedbackRepository:
    return SQLiteFeedbackRepository(settings.feedback_db_path or settings.data_dir / "feedback.db")


REPOSITORIES: dict[str, Callable[[Settings], FeedbackRepository]] = {"sqlite": _sqlite}


def build_repository(settings: Settings) -> FeedbackRepository:
    """Create the repository named by ``FEEDBACK_REPO``."""
    try:
        return REPOSITORIES[settings.feedback_repo](settings)
    except KeyError:
        raise ValueError(
            f"Unknown feedback_repo '{settings.feedback_repo}'. Options: {sorted(REPOSITORIES)}"
        ) from None


def submit(
    repo: FeedbackRepository,
    question: str,
    answer: str,
    rating: Rating,
    sources: list[str] | None = None,
    comment: str | None = None,
) -> int:
    """Store one rating; returns its id."""
    record = FeedbackRecord(
        question=question,
        answer=answer,
        rating=rating,
        sources=list(sources or []),
        comment=comment or None,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    new_id = repo.add(record)
    log.info("feedback_saved", extra={"id": new_id, "rating": rating})
    return new_id


def recent(repo: FeedbackRepository, limit: int = 20) -> list[FeedbackRecord]:
    """Newest feedback first."""
    return repo.recent(limit)
