"""Shared fixtures. Tests never read the real .env and never need an API key."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.container import Container

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Offline settings: fake embedder, reranker and LLM, in-memory store, temp data dir."""
    return Settings(
        _env_file=None,
        embedder="fake",
        reranker="fake",
        llm="fake",
        vector_store="memory",
        loader="auto",
        tokenizer="estimate",
        content_dir=REPO_ROOT / "content",
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        groq_api_key=None,
    )


@pytest.fixture
def container(settings: Settings) -> Container:
    """Container wired with offline adapters."""
    return Container(settings)


@pytest.fixture
def kb_container(tmp_path: Path, settings: Settings) -> Container:
    """Offline container whose CONTENT_DIR is an empty temp folder tests can fill."""
    content = tmp_path / "content"
    content.mkdir()
    return Container(settings.model_copy(update={"content_dir": content}))


def write(path: Path, text: str) -> Path:
    """Create parent folders and write ``text``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
