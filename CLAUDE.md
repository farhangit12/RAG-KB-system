# CLAUDE.md: Disha RAG knowledge base

RAG assistant that answers founder questions from Disha's own content (`content/`),
in Disha's warm, direct voice, with citations. Zero budget: no paid service anywhere
(decision 007). Pipeline: `docs/rag-pipeline.md`.

## How to run (Windows PowerShell)
```
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"          # add ,all for Oracle, local models, Docling
copy .env.example .env      # then fill in GROQ_API_KEY, ORACLE_*, SERVICE_API_KEY
python -m app.cli info
```

## How to test
```
ruff check .
pytest
```
Tests never need an API key, a database or a model download: use `fake` embedder,
`fake` reranker, `fake` LLM, `memory` vector store (see `tests/conftest.py`).

## Architecture rules
- **Vertical slices**: `app/features/<name>/` owns its models, service, routes and tests
  (tests mirror it under `tests/features/<name>/`). Features call each other only via
  `service.py`, never internal files.
- **Ports and adapters**: external dependencies are Protocols in `app/core/ports.py`.
  Implementations live in `app/adapters/<kind>/`. The adapter is picked by config only
  (`VECTOR_STORE`, `EMBEDDER`, `RERANKER`, `LLM`, `LOADER`, `TOKENIZER`) via registries in
  `app/core/container.py`. Feature code must never import oracledb, sentence-transformers,
  docling, chromadb, httpx clients, etc. directly.
- Config only through `app/core/config.py` (pydantic-settings). No hard-coded values.
- Logging via `app.core.logging.get_logger(__name__)` with `extra={...}` fields.
- Small typed functions; docstrings on public functions.
- Record important design choices in `docs/decisions.md`.

## How to add a new feature slice
1. Create `app/features/<name>/` with `__init__.py`, `models.py`, `service.py`, and
   `routes.py` if it has HTTP endpoints.
2. Depend on ports via the `Container`, never on concrete adapters.
3. Add tests in `tests/features/<name>/` using the fake adapters.
4. Mount the router in `app/main.py` and/or add a command in `app/cli.py`.
5. `ruff check .` and `pytest` must pass. Update this file and `docs/decisions.md`.

## How to add an adapter
Write `app/adapters/<kind>/<name>.py` with a `build(settings)` factory, add one line to
the registry in `app/core/container.py`, add a test.

## Content rules
- Markdown with YAML frontmatter: title, type, people, founder_stage, sector, topics,
  date, visibility. Missing `type` is inferred from the folder.
- PDF, DOCX, TXT, CSV: same fields in a `<file name>.meta.yaml` sidecar. Max 10 MB.
- Market reports need `publisher` and `publication_year`; `valid_until` retires old items.
- `visibility: internal` files are never indexed into the public collection.
- `visibility: private` is for one founder's uploads and needs `business_id`; the access
  filter is applied in the store query.
- **Never invent Disha content, client outcomes, numbers or quotes.**

## Safety
- Never commit secrets. Keys come only from env vars / `.env` (gitignored).
- Ask the user before adding paid services or major new dependencies. Never upgrade an
  Oracle account to Pay As You Go, and never add billing details to Groq.

## Build status
- [x] Slice 0: skeleton
- [x] Slice 1: thinnest RAG (CLI): ingest, ask
- [x] Slice 2: metadata + incremental ingestion (manifest, sidecars, private uploads)
- [x] Slice 3: HTTP API (`/ask`, uploads, delete, health; X-API-Key)
- [x] Slice 4: personalization (sector / stage / location boost, private files)
- [x] Slice 5: evaluation (hit rate at k, MRR) + backups
- [ ] Slice 6: feedback
- [ ] Slice 7: deploy readiness
