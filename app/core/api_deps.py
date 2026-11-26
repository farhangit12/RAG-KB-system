"""FastAPI dependencies shared by every feature's routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.container import Container


def get_container(request: Request) -> Container:
    """The app-wide adapter container (set in ``create_app``)."""
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]
"""Use as a route parameter type: ``container: ContainerDep``."""


def client_key(request: Request, trust_proxy_headers: bool) -> str:
    """Identify the caller by IP. Behind a proxy, use the first X-Forwarded-For entry."""
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded.strip():
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """Reject the request with 429 if this caller is over the limit."""
    container = get_container(request)
    limiter = container.rate_limiter
    if not limiter.allow(client_key(request, container.settings.trust_proxy_headers)):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute and try again.",
            headers={"Retry-After": str(limiter.window_seconds)},
        )
