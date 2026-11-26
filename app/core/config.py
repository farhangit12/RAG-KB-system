"""Application settings, read from environment variables and an optional .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All tunable values live here. Each field maps to an UPPER_CASE env var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Disha RAG"
    log_level: str = "INFO"
    log_json: bool = False

    # Paths
    content_dir: Path = Path("content")
    data_dir: Path = Path("data")
    collection_public: str = "disha_public"

    # Adapter choice: names are looked up in app/core/container.py registries.
    vector_store: str = "chroma"
    embedder: str = "chroma_default"
    llm: str = "anthropic"
    loader: str = "markdown"

    # LLM
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    llm_max_tokens: int = Field(default=8000, gt=0)
    llm_effort: str = "medium"  # low | medium | high | xhigh | max
    llm_refusal_fallback: bool = True  # retry on a fallback model if the main one declines

    # Chunking and retrieval
    chunk_size: int = Field(default=800, gt=100)
    chunk_overlap: int = Field(default=100, ge=0)
    embed_batch_size: int = Field(default=64, gt=0)
    top_k: int = Field(default=5, gt=0)

    # Personalization (Slice 4)
    retrieval_candidates: int = Field(default=20, gt=0)  # fetched before re-ranking
    boost_stage: float = 0.10  # added to the score when founder_stage matches the asker
    boost_sector: float = 0.10  # added when sector matches
    disha_path_source: str = "frameworks/disha-path.md"  # "" disables pinning
    disha_path_min_score: float = 0.30  # pin it only when at least this similar

    # API
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["https://disha-advisory-vert.vercel.app"]
    max_question_chars: int = Field(default=1000, gt=0)
    max_sector_chars: int = Field(default=60, gt=0)
    rate_limiter: str = "memory"
    rate_limit_requests: int = Field(default=20, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    trust_proxy_headers: bool = False  # true behind Render/Railway so X-Forwarded-For is used


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached after first call)."""
    return Settings()
