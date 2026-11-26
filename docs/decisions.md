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

## 010. Incremental ingestion with a manifest and a fingerprint
`DATA_DIR/manifest-<collection>.json` stores a SHA-256 per file. Unchanged files are
skipped, changed files have their old chunks deleted and are re-embedded, removed files
are deleted. A fingerprint (embedder, store, collection, chunk size/overlap, chunker
version) triggers a full rebuild when any of those change, since old vectors would be
wrong or a different size. If the store is empty but the manifest says it shouldn't be
(index wiped), it rebuilds too.

## 011. List metadata as boolean flags
`people: [Sara]` is stored as `people: "Sara"` (for display) plus `people_sara: True`
(for filtering), because list filters aren't portable across vector stores. The naming
rule lives in `app/core/metadata_keys.py`, shared by ingestion and retrieval.

## 012. Visibility enforced at query time too
Internal files are never indexed, and retrieval still always adds `visibility=public`
to every query, as a second safety layer.

## 013. API: app factory, SSE, rate limit behind a port
`create_app(settings, container)` builds the app, so tests inject fakes and nothing runs
at import time (run with `uvicorn app.main:create_app --factory`). `/chat/stream` sends
SSE events `sources`, `token`..., then `done` or `error`. The rate limiter is a
`RateLimiter` port (in-memory sliding window now; Redis later for many instances). Behind
a proxy, set `TRUST_PROXY_HEADERS=true` so the real client IP from `X-Forwarded-For` is
used. CORS allows only the origins in `CORS_ORIGINS`. Input limits are settings and
violations return 422; LLM failures return 502 with a friendly message.

## 014. Personalization is additive re-ranking
Retrieval fetches `RETRIEVAL_CANDIDATES` (20) chunks, adds `BOOST_STAGE` / `BOOST_SECTOR`
(0.10 each) to chunks whose metadata matches the asker, then keeps `TOP_K`. Boosts only
re-order relevant candidates; they never pull in chunks that weren't retrieved. The Disha
Path file (`DISHA_PATH_SOURCE`) replaces the last result when its best chunk scores at
least `DISHA_PATH_MIN_SCORE` and it's missing; this lookup applies the same filters, so
an explicit `type=faq` filter is respected. Tune these values with `cli eval`.

## 015. Evaluation measures retrieval automatically, answers by human reading
Hit rate per question = share of `expected_sources` found among the retrieved files
(the same pipeline as chat, including personalization). Questions with no expected
sources (out of scope) are reported but not scored. Answer quality (voice, citations, no
invented numbers) is judged by a person reading `reports/eval-*.md`, since an automatic
judge would cost API calls and need its own calibration. `--no-answers` runs for free.

## 006. Settings read the API key into `SecretStr`
`ANTHROPIC_API_KEY` is read by pydantic-settings and passed explicitly to the client, so
it works from `.env` as well as real env vars, and is never printed in logs or `repr`.
