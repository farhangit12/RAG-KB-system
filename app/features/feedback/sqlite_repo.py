"""SQLite implementation of FeedbackRepository (standard library only).

A new connection is opened per operation, so it is safe across FastAPI worker threads.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.features.feedback.models import FeedbackRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    comment TEXT
)
"""


class SQLiteFeedbackRepository:
    """Feedback table in one SQLite file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def add(self, record: FeedbackRecord) -> int:
        """Insert a record; returns its id."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO feedback (created_at, question, answer, sources, rating, comment)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.created_at,
                    record.question,
                    record.answer,
                    json.dumps(record.sources),
                    record.rating,
                    record.comment,
                ),
            )
            return int(cur.lastrowid or 0)

    def recent(self, limit: int = 20) -> list[FeedbackRecord]:
        """Newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, created_at, question, answer, sources, rating, comment"
                " FROM feedback ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            FeedbackRecord(
                id=r[0],
                created_at=r[1],
                question=r[2],
                answer=r[3],
                sources=json.loads(r[4]),
                rating=r[5],
                comment=r[6],
            )
            for r in rows
        ]
