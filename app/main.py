"""HTTP API. Run: ``uvicorn app.main:app --port 8100``."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.container import Container
from app.core.logging import configure_logging
from app.features.chat.routes import router as chat_router
from app.features.ingestion.routes import router as ingestion_router
from app.web import get_container, require_api_key


def create_app() -> FastAPI:
    """Build the FastAPI app with every feature router mounted."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    api = FastAPI(title=settings.app_name)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    protected = [Depends(require_api_key)]
    api.include_router(chat_router, dependencies=protected)
    api.include_router(ingestion_router, dependencies=protected)

    @api.get("/health")
    def health(container: Container = Depends(get_container)) -> dict:
        """Liveness plus a store round-trip (also keeps the free database from idling)."""
        return {"status": "ok", "chunks": container.vector_store.count()}

    return api


app = create_app()
