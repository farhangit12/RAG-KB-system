"""Shared fixtures. Tests never read the real .env and never need an API key."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.container import Container

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Offline settings: fake embedder and LLM, in-memory store, temp data dir."""
    return Settings(
        _env_file=None,
        embedder="fake",
        llm="fake",
        vector_store="memory",
        content_dir=REPO_ROOT / "content",
        data_dir=tmp_path / "data",
        anthropic_api_key=None,
    )


@pytest.fixture
def container(settings: Settings) -> Container:
    """Container wired with offline adapters."""
    return Container(settings)
