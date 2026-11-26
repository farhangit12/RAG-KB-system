-- Disha KB chunks for Oracle AI Database 26ai (Always Free Autonomous AI Database, Account 1).
-- Created by `python -m app.cli init-db`, or run by hand as the KB schema owner.
-- No semicolons inside statements: the loader splits on them.

CREATE TABLE kb_chunks (
    id          VARCHAR2(400)  PRIMARY KEY,
    collection  VARCHAR2(100)  NOT NULL,
    source      VARCHAR2(1000) NOT NULL,
    chunk_text  CLOB           NOT NULL,
    metadata    JSON           NOT NULL,
    embedding   VECTOR(1024, FLOAT32) NOT NULL,
    created_at  TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at  TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE INDEX kb_chunks_source_ix ON kb_chunks (collection, source);

-- Filter fields used on every search (access, private owner, type).
CREATE INDEX kb_chunks_visibility_ix ON kb_chunks (JSON_VALUE(metadata, '$.visibility'));

CREATE INDEX kb_chunks_business_ix ON kb_chunks (JSON_VALUE(metadata, '$.business_id'));

-- Keyword search for exact names (schemes, companies). Synced on every commit.
CREATE INDEX kb_chunks_text_ix ON kb_chunks (chunk_text)
    INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS ('SYNC (ON COMMIT)');

-- Vector index: not needed while the KB is small (exact search is fine below about
-- 50,000 chunks). When it grows, run this by hand and set ORACLE_APPROX_SEARCH=true:
--
-- CREATE VECTOR INDEX kb_chunks_vec_ix ON kb_chunks (embedding)
--     ORGANIZATION NEIGHBOR PARTITIONS DISTANCE COSINE WITH TARGET ACCURACY 95
