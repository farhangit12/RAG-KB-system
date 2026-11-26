from __future__ import annotations

import pytest

from app.adapters.embedders.fake import FakeEmbedder
from app.adapters.vectorstores.chroma_store import chroma_where
from app.adapters.vectorstores.memory_store import MemoryVectorStore
from app.adapters.vectorstores.oracle_store import OracleVectorStore, contains_query, where_sql
from app.core.ports import Chunk, Exportable, KeywordSearch


def test_oracle_where_sql_binds_every_value() -> None:
    sql, binds = where_sql({"visibility": "private", "business_id": "b1", "type": ["faq", "story"]})
    assert sql == (" AND JSON_VALUE(metadata, '$.visibility') = :f0"
                   " AND JSON_VALUE(metadata, '$.business_id') = :f1"
                   " AND JSON_VALUE(metadata, '$.type') IN (:f2, :f3)")
    assert binds == {"f0": "private", "f1": "b1", "f2": "faq", "f3": "story"}
    assert where_sql({"flag": True})[1] == {"f0": "true"}
    assert where_sql(None) == ("", {})


def test_oracle_rejects_unsafe_keys_and_tables(settings) -> None:
    with pytest.raises(ValueError, match="Invalid metadata key"):
        where_sql({"x') OR 1=1 --": "a"})
    bad = settings.model_copy(update={"oracle_table": "kb; DROP TABLE x"})
    with pytest.raises(ValueError, match="ORACLE_TABLE"):
        OracleVectorStore(bad, connection=object())


def test_contains_query_escapes_terms() -> None:
    assert contains_query("What is the Startup India Seed Fund?") == (
        "{startup} ACCUM {india} ACCUM {seed} ACCUM {fund}"
    )
    assert contains_query("is it?") == ""


def test_chroma_where_translation() -> None:
    assert chroma_where(None) is None
    assert chroma_where({"visibility": "public"}) == {"visibility": {"$eq": "public"}}
    assert chroma_where({"a": 1, "b": ["x", "y"]}) == {
        "$and": [{"a": {"$eq": 1}}, {"b": {"$in": ["x", "y"]}}]
    }


def test_memory_store_keyword_search_and_export() -> None:
    store = MemoryVectorStore()
    assert isinstance(store, KeywordSearch)
    assert isinstance(store, Exportable)
    chunks = [Chunk("a#0", "a", "Startup India Seed Fund Scheme", {"v": "x"}),
              Chunk("b#0", "b", "pricing your first product", {"v": "y"})]
    store.upsert(chunks, FakeEmbedder().embed([c.text for c in chunks]))
    [hit] = store.keyword_query("seed fund", top_k=5)
    assert hit.chunk.id == "a#0"
    assert store.keyword_query("seed fund", top_k=5, where={"v": "y"}) == []
    assert len(list(store.export_items())) == 2


class _Cursor:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: object = None) -> None:
        if "kb_chunks_source_ix" in sql:
            raise RuntimeError("ORA-00955: name is already used by an existing object")
        self.log.append(" ".join(sql.split()))


class _Conn:
    def __init__(self) -> None:
        self.log: list[str] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self.log)

    def commit(self) -> None:
        pass


def test_oracle_create_schema_runs_each_statement_once(settings) -> None:
    conn = _Conn()
    OracleVectorStore(settings, connection=conn).create_schema()
    assert conn.log[0].startswith("CREATE TABLE kb_chunks")
    assert "VECTOR(1024, FLOAT32)" in conn.log[0]
    assert any("CTXSYS.CONTEXT" in s for s in conn.log)
    assert not any("CREATE VECTOR INDEX" in s for s in conn.log)  # commented out until needed
    assert len(conn.log) == 4  # table + 3 indexes run; the existing one was skipped
