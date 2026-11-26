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

## 007. Chunking: headings, then paragraphs
Each chunk is prefixed with its heading path ("The Disha Path > 2. Talk to ten real
people") so it still makes sense when retrieved alone. Paragraphs are packed up to
`CHUNK_SIZE` (800) characters; long paragraphs split at sentence ends; consecutive
chunks of a section share `CHUNK_OVERLAP` (100) characters.

## 008. Claude adapter: effort + refusal fallback
The Anthropic adapter sends `output_config.effort` (`LLM_EFFORT`, default `medium`) and,
with `LLM_REFUSAL_FALLBACK=true`, the server-side fallback beta (`fallbacks: "default"`),
so a safety decline is retried on a fallback model in the same call. If the whole chain
declines, the user gets a short message pointing to a Direction Call. API errors become
`LLMError` so features never import the SDK.

## 009. One contract test for all vector stores
`tests/adapters/test_vectorstore_contract.py` runs the same tests against every
VectorStore adapter. A new adapter is "swappable" when it passes that file.

## 006. Settings read the API key into `SecretStr`
`ANTHROPIC_API_KEY` is read by pydantic-settings and passed explicitly to the client, so
it works from `.env` as well as real env vars, and is never printed in logs or `repr`.
