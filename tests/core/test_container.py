from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.container import AdapterNotFoundError, Container
from app.core.ports import LLM, Embedder, VectorStore


def test_builds_configured_adapters(container: Container) -> None:
    assert isinstance(container.embedder, Embedder)
    assert isinstance(container.vector_store, VectorStore)
    assert isinstance(container.llm, LLM)


def test_adapters_are_created_once(container: Container) -> None:
    assert container.vector_store is container.vector_store


def test_unknown_adapter_gives_clear_error(settings: Settings) -> None:
    bad = Container(settings.model_copy(update={"vector_store": "nope"}))
    with pytest.raises(AdapterNotFoundError, match="Unknown vector_store 'nope'"):
        _ = bad.vector_store
