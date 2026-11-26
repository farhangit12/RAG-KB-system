"""Builds concrete adapters from config.

Each registry maps a config name (e.g. ``VECTOR_STORE=memory``) to a factory path
``"module:function"``. Factories take ``Settings`` and return an adapter. Modules are
imported lazily, so heavy libraries load only when that adapter is actually chosen.

To add an adapter: write it under ``app/adapters/``, give it a ``build(settings)``
function, and add one line to the right registry below.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import cached_property
from typing import Any

from app.core.config import Settings, get_settings
from app.core.ports import LLM, DocumentLoader, Embedder, RateLimiter, VectorStore

EMBEDDERS: dict[str, str] = {
    "chroma_default": "app.adapters.embedders.chroma_default:build",
    "fake": "app.adapters.embedders.fake:build",
}
VECTOR_STORES: dict[str, str] = {
    "chroma": "app.adapters.vectorstores.chroma_store:build",
    "memory": "app.adapters.vectorstores.memory_store:build",
}
LLMS: dict[str, str] = {
    "anthropic": "app.adapters.llms.anthropic_llm:build",
    "fake": "app.adapters.llms.fake:build",
}
LOADERS: dict[str, str] = {
    "markdown": "app.adapters.loaders.markdown_loader:build",
}
RATE_LIMITERS: dict[str, str] = {
    "memory": "app.adapters.ratelimiters.memory:build",
}


class AdapterNotFoundError(ValueError):
    """Raised when config names an adapter that is not registered."""


def _resolve(kind: str, name: str, registry: dict[str, str]) -> Callable[[Settings], Any]:
    try:
        target = registry[name]
    except KeyError:
        options = ", ".join(sorted(registry)) or "none yet"
        raise AdapterNotFoundError(f"Unknown {kind} '{name}'. Options: {options}") from None
    module_name, attr = target.split(":")
    return getattr(importlib.import_module(module_name), attr)


class Container:
    """Holds one instance of each adapter, created on first use."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def embedder(self) -> Embedder:
        """The configured Embedder."""
        return _resolve("embedder", self.settings.embedder, EMBEDDERS)(self.settings)

    @cached_property
    def vector_store(self) -> VectorStore:
        """The configured VectorStore."""
        return _resolve("vector_store", self.settings.vector_store, VECTOR_STORES)(self.settings)

    @cached_property
    def llm(self) -> LLM:
        """The configured LLM."""
        return _resolve("llm", self.settings.llm, LLMS)(self.settings)

    @cached_property
    def loader(self) -> DocumentLoader:
        """The configured DocumentLoader."""
        return _resolve("loader", self.settings.loader, LOADERS)(self.settings)

    @cached_property
    def rate_limiter(self) -> RateLimiter:
        """The configured RateLimiter."""
        return _resolve("rate_limiter", self.settings.rate_limiter, RATE_LIMITERS)(self.settings)


def build_container(settings: Settings | None = None) -> Container:
    """Create a container from the given settings (or the global ones)."""
    return Container(settings or get_settings())
