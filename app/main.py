"""FastAPI app. Run: ``uvicorn app.main:create_app --factory`` (or ``python -m app.cli serve``).

The app is stateless apart from the in-memory rate limiter, so several instances can
run behind a load balancer (move the limiter to Redis when you do).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.container import Container, build_container
from app.core.logging import configure_logging
from app.features.chat.routes import router as chat_router


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build the API with every feature router mounted."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.state.container = container or build_container(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(chat_router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Liveness check."""
        return {"status": "ok"}

    return app
