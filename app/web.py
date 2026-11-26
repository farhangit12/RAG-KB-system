"""Shared FastAPI dependencies (container and API-key check)."""

from __future__ import annotations

import secrets
from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from app.core.container import Container, build_container


@lru_cache
def _container() -> Container:
    return build_container()


def get_container() -> Container:
    """The process-wide container (overridden in tests)."""
    return _container()


def require_api_key(
    x_api_key: str | None = Header(default=None),
    container: Container = Depends(get_container),
) -> None:
    """Reject the request unless it carries SERVICE_API_KEY (when one is configured)."""
    expected = container.settings.service_api_key
    if expected is None:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected.get_secret_value()):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
