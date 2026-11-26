from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.container import Container
from app.features.feedback import service
from app.features.feedback.ports import FeedbackRepository
from app.features.feedback.sqlite_repo import SQLiteFeedbackRepository
from app.main import create_app

GOOD = {
    "question": "What is the Disha Path?",
    "answer": "Four steps... [The Disha Path]",
    "sources": ["frameworks/disha-path.md"],
    "rating": "up",
    "comment": "Clear!",
}


def test_sqlite_repo_roundtrip(tmp_path: Path) -> None:
    repo = SQLiteFeedbackRepository(tmp_path / "fb.db")
    assert isinstance(repo, FeedbackRepository)
    first = service.submit(repo, "q1", "a1", "up", ["x.md"])
    second = service.submit(repo, "q2", "a2", "down", comment="too vague")
    rows = service.recent(repo)
    assert [r.id for r in rows] == [second, first]
    assert rows[0].comment == "too vague"
    assert rows[1].sources == ["x.md"]
    assert rows[0].created_at.endswith("+00:00")


def test_data_survives_a_new_repository_instance(tmp_path: Path) -> None:
    service.submit(SQLiteFeedbackRepository(tmp_path / "fb.db"), "q", "a", "up")
    assert len(SQLiteFeedbackRepository(tmp_path / "fb.db").recent()) == 1


def test_unknown_repository_name(container: Container) -> None:
    with pytest.raises(ValueError, match="Unknown feedback_repo"):
        service.build_repository(container.settings.model_copy(update={"feedback_repo": "x"}))


@pytest.fixture
def client(container: Container) -> TestClient:
    return TestClient(create_app(container.settings, container))


def test_post_feedback_is_stored(client: TestClient, container: Container) -> None:
    res = client.post("/feedback", json=GOOD)
    assert res.status_code == 201
    new_id = res.json()["id"]
    repo = SQLiteFeedbackRepository(container.settings.data_dir / "feedback.db")
    [row] = repo.recent()
    assert row.id == new_id
    assert row.rating == "up"
    assert row.sources == ["frameworks/disha-path.md"]


@pytest.mark.parametrize(
    "change",
    [
        {"rating": "meh"},
        {"question": ""},
        {"answer": "a" * 20001},
        {"comment": "c" * 1001},
        {"sources": ["s"] * 21},
        {"sources": ["s" * 301]},
        {"user_ip": "1.2.3.4"},
    ],
)
def test_feedback_validation(client: TestClient, change: dict) -> None:
    assert client.post("/feedback", json={**GOOD, **change}).status_code == 422
