from __future__ import annotations

from app.core.container import Container
from app.core.ports import Chunk
from app.features.backup.service import export_jsonl, restore_jsonl


def test_export_and_restore_round_trip(container: Container) -> None:
    chunks = [Chunk(f"s#{i}", "s", f"text {i}", {"visibility": "public", "chunk_index": i})
              for i in range(3)]
    container.vector_store.upsert(chunks, container.embedder.embed([c.text for c in chunks]))
    path = export_jsonl(container)
    assert path.name.endswith(".jsonl.gz")

    fresh = Container(container.settings)
    assert restore_jsonl(fresh, path) == 3
    assert fresh.vector_store.count() == 3
    original = {c.id: (c, v) for c, v in container.vector_store.export_items()}
    for chunk, vec in fresh.vector_store.export_items():
        assert original[chunk.id] == (chunk, vec)
