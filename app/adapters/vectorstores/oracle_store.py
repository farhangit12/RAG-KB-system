"""Oracle AI Vector Search store (production KB DB).

Runs on the Always Free Autonomous AI Database in Account 1 (20 GB). Oracle Database Free on
a VM is NOT used for the KB: it allows 12 GB of user data and one installation per machine,
and VM-A's database already holds Alpha DB (decision 009).

Table layout is in ``sql/oracle/001_kb_chunks.sql``. Each chunk row has its text (CLOB),
scalar metadata (JSON), one VECTOR(1024, FLOAT32) and a collection name. Keyword search uses
an Oracle Text index on the chunk text. Needs the ``oracle`` extra (python-oracledb, thin mode,
no Oracle client install).
"""

from __future__ import annotations

import array
import json
import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.ports import Chunk, Filter, MetadataValue, ScoredChunk
from app.core.text import keyword_terms

log = get_logger(__name__)

_KEY = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")
_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,127}$")
SCHEMA_FILE = Path(__file__).resolve().parents[3] / "sql" / "oracle" / "001_kb_chunks.sql"


def _bind_value(value: MetadataValue) -> str:
    """JSON_VALUE returns text, so every filter value is compared as text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def where_sql(where: Filter | None, start: int = 0) -> tuple[str, dict[str, str]]:
    """Translate a ports.Filter into ``AND ...`` SQL plus bind values. Keys are validated."""
    if not where:
        return "", {}
    parts: list[str] = []
    binds: dict[str, str] = {}
    n = start
    for key, expected in where.items():
        if not _KEY.match(key):
            raise ValueError(f"Invalid metadata key for filtering: {key!r}")
        column = f"JSON_VALUE(metadata, '$.{key}')"
        values = list(expected) if isinstance(expected, list | tuple | set) else [expected]
        names = []
        for v in values:
            name = f"f{n}"
            n += 1
            binds[name] = _bind_value(v)
            names.append(f":{name}")
        if not names:
            parts.append("1 = 0")
        elif len(names) == 1:
            parts.append(f"{column} = {names[0]}")
        else:
            parts.append(f"{column} IN ({', '.join(names)})")
    return " AND " + " AND ".join(parts), binds


def contains_query(text: str) -> str:
    """Oracle Text query: each term escaped with braces, joined with ACCUM (any term scores)."""
    return " ACCUM ".join("{" + t + "}" for t in keyword_terms(text))


class OracleVectorStore:
    """VectorStore + KeywordSearch + Exportable on Oracle AI Database 26ai."""

    def __init__(self, settings: Settings, connection: Any | None = None) -> None:
        if not _TABLE.match(settings.oracle_table):
            raise ValueError(f"Invalid ORACLE_TABLE: {settings.oracle_table!r}")
        self._table = settings.oracle_table
        self._collection = settings.collection_public
        self._dim = settings.embed_dim
        self._approx = "APPROX " if settings.oracle_approx_search else ""
        self._conn = connection or self._connect(settings)

    @staticmethod
    def _connect(s: Settings) -> Any:
        import oracledb

        oracledb.defaults.fetch_lobs = False  # CLOB arrives as str
        kwargs: dict[str, Any] = {
            "user": s.oracle_user,
            "password": s.oracle_password.get_secret_value() if s.oracle_password else None,
            "dsn": s.oracle_dsn,
        }
        if s.oracle_wallet_dir:
            kwargs.update(config_dir=s.oracle_wallet_dir, wallet_location=s.oracle_wallet_dir)
            if s.oracle_wallet_password:
                kwargs["wallet_password"] = s.oracle_wallet_password.get_secret_value()
        return oracledb.connect(**kwargs)

    # ------------------------------------------------------------------ schema
    def create_schema(self) -> None:
        """Run the schema file once; objects that already exist are skipped."""
        text = SCHEMA_FILE.read_text(encoding="utf-8").replace("kb_chunks", self._table)
        lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("--")]
        statements = [st.strip() for st in "\n".join(lines).split(";") if st.strip()]
        with self._conn.cursor() as cur:
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except Exception as exc:  # ORA-00955 / ORA-01408: already exists
                    if "ORA-00955" in str(exc) or "ORA-01408" in str(exc):
                        continue
                    raise
        self._conn.commit()

    # ------------------------------------------------------------------ writes
    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """MERGE by chunk id, so re-ingesting a file replaces its chunks."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        rows = []
        for c, e in zip(chunks, embeddings, strict=True):
            if len(e) != self._dim:
                raise ValueError(f"vector for {c.id} has {len(e)} dims, expected {self._dim}")
            rows.append(
                {
                    "id": c.id,
                    "coll": self._collection,
                    "source": c.source,
                    "body": c.text,
                    "meta": json.dumps(c.metadata, ensure_ascii=False),
                    "vec": array.array("f", e),
                }
            )
        sql = f"""
            MERGE INTO {self._table} t
            USING (SELECT :id AS id FROM dual) s ON (t.id = s.id)
            WHEN MATCHED THEN UPDATE SET collection = :coll, source = :source,
                 chunk_text = :body, metadata = :meta, embedding = :vec,
                 updated_at = SYSTIMESTAMP
            WHEN NOT MATCHED THEN INSERT (id, collection, source, chunk_text, metadata, embedding)
                 VALUES (:id, :coll, :source, :body, :meta, :vec)"""
        with self._conn.cursor() as cur:
            cur.executemany(sql, rows)
        self._conn.commit()

    def delete_by_source(self, source: str) -> None:
        """Remove every chunk (and its vector) from one source file."""
        with self._conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {self._table} WHERE collection = :coll AND source = :source",
                {"coll": self._collection, "source": source},
            )
        self._conn.commit()

    # ------------------------------------------------------------------ reads
    def query(
        self, embedding: Sequence[float], top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Cosine nearest neighbours; score = 1 - cosine distance."""
        extra, binds = where_sql(where)
        sql = f"""
            SELECT id, source, chunk_text, metadata,
                   VECTOR_DISTANCE(embedding, :qv, COSINE) AS dist
            FROM {self._table}
            WHERE collection = :coll{extra}
            ORDER BY dist
            FETCH {self._approx}FIRST :k ROWS ONLY"""
        params = {"qv": array.array("f", embedding), "coll": self._collection, "k": top_k, **binds}
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._row(r, 1.0 - float(r[4])) for r in cur.fetchall()]

    def keyword_query(
        self, text: str, top_k: int, where: Filter | None = None
    ) -> list[ScoredChunk]:
        """Oracle Text CONTAINS search; score scaled to [0, 1]."""
        q = contains_query(text)
        if not q:
            return []
        extra, binds = where_sql(where)
        sql = f"""
            SELECT id, source, chunk_text, metadata, SCORE(1) AS sc
            FROM {self._table}
            WHERE collection = :coll AND CONTAINS(chunk_text, :q, 1) > 0{extra}
            ORDER BY sc DESC
            FETCH FIRST :k ROWS ONLY"""
        params = {"coll": self._collection, "q": q, "k": top_k, **binds}
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._row(r, float(r[4]) / 100.0) for r in cur.fetchall()]

    def count(self) -> int:
        """Number of chunks in this collection."""
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {self._table} WHERE collection = :coll",
                {"coll": self._collection},
            )
            return int(cur.fetchone()[0])

    def export_items(self) -> Iterator[tuple[Chunk, list[float]]]:
        """Yield every chunk with its vector, for the JSONL backup."""
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT id, source, chunk_text, metadata, embedding FROM {self._table} "
                "WHERE collection = :coll ORDER BY source, id",
                {"coll": self._collection},
            )
            for r in cur:
                yield self._row(r, 0.0).chunk, list(r[4])

    @staticmethod
    def _row(r: Sequence[Any], score: float) -> ScoredChunk:
        meta = r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}")
        return ScoredChunk(chunk=Chunk(id=r[0], source=r[1], text=r[2], metadata=meta), score=score)


def build(settings: Settings) -> OracleVectorStore:
    """Factory used by the container."""
    return OracleVectorStore(settings)
