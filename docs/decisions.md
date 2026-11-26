# Design decisions

Short records of choices that shape the code. Newest at the bottom.

## 001. Vertical slices
Code is grouped by feature (`app/features/<name>/`), not by layer. A feature imports
another feature only through its `service.py`. This keeps each feature removable and
testable alone.

## 002. Ports and adapters with a lazy registry
Every external dependency is a `Protocol` in `app/core/ports.py`. `app/core/container.py`
maps config names to `"module:build"` strings and imports them only when chosen. So
heavy libraries (chromadb, anthropic) load only if configured, and swapping an adapter
is a config change plus one registry line.

## 003. Chunk metadata is scalar only
Chunk metadata values are `str | int | float | bool`, because not every vector store
can filter on lists. List fields from frontmatter (e.g. `people`, `topics`) will be
flattened when chunks are built (Slice 2).

## 004. Fake adapters ship with the app
`fake` embedder, `fake` LLM and `memory` vector store live in `app/adapters/` (not only in
tests) so the whole pipeline can run offline, with no API key, for tests and demos.

## 005. pip + venv instead of uv
uv was not installed on the dev machine, so setup uses `python -m venv` and
`pip install -e ".[dev]"`. `pyproject.toml` is standard, so uv works too if installed later.

## 006. Settings read the API key into `SecretStr`
`ANTHROPIC_API_KEY` is read by pydantic-settings and passed explicitly to the client, so
it works from `.env` as well as real env vars, and is never printed in logs or `repr`.

## 007. Zero-budget stack by default
Disha will not pay for APIs, subscriptions, hosting or databases. Defaults are now:
Oracle AI Vector Search (Always Free Autonomous AI Database), bge-m3 embeddings and
bge-reranker-v2-m3 run locally, and Groq's free plan for generation. The `anthropic`
dependency was removed; Chroma stays as an optional local store (`chroma` extra).
Heavy libraries are optional extras (`oracle`, `models`, `docs`), so tests stay offline.

## 008. Token-based chunking: 500 tokens, 75 overlap
Chunks are measured in tokens, not characters: 500 with a 75-token overlap (a new chunk
every 425). Headings and paragraphs are split first; tables stay whole (or are split by
rows with the header repeated). `TOKENIZER=estimate` errs high and needs no download;
`TOKENIZER=hf` counts exactly with the bge-m3 tokenizer.

## 009. KB lives in the Autonomous database, not in VM-A's Oracle Database Free
Oracle Database Free caps user data at 12 GB and allows one installation per machine.
VM-A's database already holds Alpha DB (up to 8 GB), so the 6 GB KB goes into Account 1's
Always Free Autonomous AI Database (20 GB). That database has no backup or restore of its
own, so `app.cli backup` exports JSONL (text, metadata, vectors) for Account 4's Object
Storage, and the original files are kept so the KB can always be rebuilt.

## 010. Docling instead of PyMuPDF
PyMuPDF is AGPL: a closed-source web service would have to publish its source or buy a
licence. Docling (MIT) extracts PDF and DOCX with headings, tables and OCR. pypdf (BSD) and
python-docx (MIT) are fallbacks when Docling is not installed.

## 011. Other file types carry metadata in a sidecar
PDF, DOCX, TXT and CSV files get metadata from `<file name>.meta.yaml` next to them, with
the same fields as markdown frontmatter. Editing the sidecar re-indexes the file.

## 012. Three visibilities, enforced in the query
`public` (everyone), `internal` (never indexed) and `private` (one `business_id`).
Retrieval runs one search for public chunks and one for the asking business's private
chunks; the filter is part of the store query, never only an instruction to the model.

## 013. Hybrid search, fusion, rerank, threshold
Vector search finds meaning; keyword search (Oracle Text) finds exact names such as scheme
titles. Ranks are fused with RRF, nudged by sector/stage/location matches, then reranked by
a cross-encoder. Only chunks scoring at least `RERANK_MIN_SCORE` are used; if none pass,
a fixed "not in the knowledge base" answer is returned without calling the LLM.

## 014. Citations are checked after generation
Sources are labelled [S1]..[Sn] with title, page, publisher and year. Labels the model
invents are removed, and an answer with no valid citation is flagged `low_confidence`.

## 015. Founder uploads are private files under DATA_DIR/uploads/<business_id>/
The API saves uploads there and indexes them with `visibility: private`. Every API call
needs `X-API-Key` when `SERVICE_API_KEY` is set: the main Disha backend calls this service,
founders never call it directly.
