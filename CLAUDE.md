# CLAUDE.md: Disha RAG knowledge base

RAG assistant that answers founder questions from Disha's own content (`content/`),
in Disha's warm, direct voice, with citations.

## How to run (Windows PowerShell)
```
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env      # then fill in ANTHROPIC_API_KEY
python -m app.cli info
```

## How to test
```
ruff check .
pytest
```
Tests never need an API key: use `fake` embedder, `fake` LLM, `memory` vector store
(see `tests/conftest.py`).

## Architecture rules
- **Vertical slices**: `app/features/<name>/` owns its models, service, routes and tests
  (tests mirror it under `tests/features/<name>/`). Features call each other only via
  `service.py`, never internal files.
- **Ports and adapters**: external dependencies are Protocols in `app/core/ports.py`.
  Implementations live in `app/adapters/<kind>/`. The adapter is picked by config only
  (`VECTOR_STORE`, `EMBEDDER`, `LLM`, `LOADER`) via registries in `app/core/container.py`.
  Feature code must never import chromadb, anthropic, etc. directly.
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
- `visibility: internal` files are never indexed into the public collection.
- **Never invent Disha content, client outcomes, numbers or quotes.**

## Safety
- Never commit secrets. The API key comes only from env vars / `.env` (gitignored).
- Ask the user before adding paid services or major new dependencies.

## Build status
- [x] Slice 0: skeleton
- [ ] Slice 1: thinnest RAG (CLI)
- [ ] Slice 2: metadata + incremental ingestion
- [ ] Slice 3: HTTP API
- [ ] Slice 4: personalization
- [ ] Slice 5: evaluation
- [ ] Slice 6: feedback
- [ ] Slice 7: deploy readiness
