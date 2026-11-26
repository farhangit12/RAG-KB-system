from __future__ import annotations

import pytest

from app.core.config import Settings


def test_defaults_match_spec() -> None:
    s = Settings(_env_file=None)
    assert s.vector_store == "chroma"
    assert s.embedder == "chroma_default"
    assert s.llm == "anthropic"
    assert s.anthropic_model == "claude-sonnet-5-5"
    assert s.chunk_size == 800
    assert s.cors_origins == ["https://disha-advisory-vert.vercel.app"]


def test_env_vars_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_STORE", "memory")
    monkeypatch.setenv("TOP_K", "9")
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example", "https://b.example"]')
    s = Settings(_env_file=None)
    assert s.vector_store == "memory"
    assert s.top_k == 9
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_api_key_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    s = Settings(_env_file=None)
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-test-123"
    assert "sk-test-123" not in repr(s)


def test_invalid_values_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, chunk_size=10)
