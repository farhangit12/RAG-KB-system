"""Application settings, read from environment variables and an optional .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
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
    # Defaults are the zero-budget stack (decision 007): no paid API anywhere.
    vector_store: str = "oracle"
    embedder: str = "bge_m3"
    reranker: str = "bge"
    llm: str = "groq"
    loader: str = "auto"
    tokenizer: str = "estimate"

    # LLM (Groq free plan, OpenAI-compatible API)
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_s: float = Field(default=60.0, gt=0)
    groq_max_retries: int = Field(default=3, ge=0)
    llm_max_tokens: int = Field(default=1500, gt=0)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)

    # Local models (run on our own VM, so no API cost)
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = Field(default=1024, gt=0)
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    model_device: str = "cpu"

    # Oracle KB DB (Account 1 Always Free Autonomous AI Database)
    oracle_user: str = ""
    oracle_password: SecretStr | None = None
    oracle_dsn: str = ""
    oracle_wallet_dir: str = ""
    oracle_wallet_password: SecretStr | None = None
    oracle_table: str = "kb_chunks"
    oracle_approx_search: bool = False   # turn on after the vector index is created

    # Upload rules
    max_file_mb: int = Field(default=10, gt=0)

    # Chunking (tokens): 500 with 75 overlap, so a new chunk every 425 tokens
    chunk_size: int = Field(default=500, gt=100)
    chunk_overlap: int = Field(default=75, ge=0)
    csv_rows_per_block: int = Field(default=25, gt=0)
    embed_batch_size: int = Field(default=16, gt=0)

    # Retrieval
    top_k: int = Field(default=20, gt=0)            # candidates from each search
    rrf_k: int = Field(default=60, gt=0)            # reciprocal rank fusion constant
    profile_boost: float = Field(default=0.15, ge=0)
    rerank_keep: int = Field(default=3, gt=0)
    rerank_min_score: float = Field(default=0.2, ge=0, le=1)

    # Packing: the sources must fit inside one Groq call (6,000 input tokens in total)
    pack_token_budget: int = Field(default=1500, gt=0)
    max_input_tokens: int = Field(default=6000, gt=0)

    # Backups (JSONL export; copy the folder to Account 4 Object Storage)
    backup_dir: Path = Path("data/backups")

    # API: when set, every request must send it in the X-API-Key header.
    # The main Disha backend calls this service; founders never call it directly.
    service_api_key: SecretStr | None = None
    max_upload_mb: int = Field(default=10, gt=0)

    # API
    cors_origins: list[str] = ["https://disha-advisory-vert.vercel.app"]

    @model_validator(mode="after")
    def _overlap_below_size(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached after first call)."""
    return Settings()
