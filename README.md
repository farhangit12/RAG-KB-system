# RAG-KB-system
# Disha RAG Knowledge Base

An AI assistant that answers questions from students and first-time founders using
[Disha Startup Advisory](https://disha-advisory-vert.vercel.app)'s own stories, frameworks,
case studies and FAQs, in Disha's warm, direct voice, **with citations**. It never invents
Disha content, client outcomes, numbers or quotes. When the knowledge base doesn't cover a
question, it says so and points the founder to a ₹99 Direction Call.

## Contents
1. [Branches](#branches)
2. [How it works](#how-it-works)
3. [Tech stack](#tech-stack)
4. [Quick start](#quick-start)
5. [Commands](#commands)
6. [HTTP API](#http-api)
7. [Adding content](#adding-content)
8. [Project layout](#project-layout)
9. [Architecture rules](#architecture-rules)
10. [Documentation](#documentation)
11. [Status and next steps](#status-and-next-steps)

## Branches

| Branch | What it holds |
| --- | --- |
| `main` | This overview |
| `dev0` | Slices 0 to 7: ingestion, retrieval, chat (with streaming), evaluation, feedback, deploy guide. Uses Anthropic Claude and Chroma |
| `rag-pipeline` | Zero-budget version: Oracle AI Vector Search, local bge-m3 embeddings and bge reranker, Groq free plan, PDF/DOCX/TXT/CSV ingestion, private founder uploads, backups |

The two working branches share the same skeleton (decisions 001 to 006) and then diverge.
Merging `rag-pipeline` into `dev0` needs a manual pass (both changed config, chunking and
`docs/decisions.md`).

## How it works

```
Write path:  file → validate → load → clean → chunk → metadata → embed → vector store
Read path:   question → search (with access filters) → personalise → rank
             → pack sources → LLM → answer with citations
```

1. **Ingest.** Files in `content/` are split by headings and paragraphs into chunks, each
   starting with its heading path. Only new or changed files are re-indexed.
2. **Search.** A question finds the closest chunks. Only `public` content is searchable;
   `internal` files are never indexed.
3. **Personalise.** Chunks matching the founder's stage and sector rank higher.
4. **Answer.** The model answers from the retrieved sources only and cites them.

Full step-by-step diagrams: `docs/rag-pipeline.md` (on `rag-pipeline`).

## Tech stack

| Part | `dev0` | `rag-pipeline` (zero budget) |
| --- | --- | --- |
| Language | Python 3.13 | Python 3.13 |
| API | FastAPI | FastAPI |
| Answer model | Anthropic Claude | Groq free plan |
| Embeddings | Chroma's default local model | bge-m3, local (1,024 numbers per chunk) |
| Reranking | Stage and sector boosts | bge-reranker-v2-m3, local |
| Vector store | Chroma (Qdrant optional) | Oracle AI Vector Search (Chroma optional) |
| Hosting | Docker on Render or Railway | Oracle Cloud Always Free |

## Quick start

Windows PowerShell (use `python3` and `source .venv/bin/activate` on Mac/Linux):

```
git clone https://github.com/farhangit12/RAG-KB-system.git
cd RAG-KB-system
git checkout dev0            # or: git checkout rag-pipeline
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```

Then open `.env` and add your key:
- `dev0`: `ANTHROPIC_API_KEY`
- `rag-pipeline`: `GROQ_API_KEY`, plus `ORACLE_*` and `SERVICE_API_KEY` for production
  (install production extras with `python -m pip install -e ".[dev,all]"`)

Check it works:
```
python -m app.cli info
ruff check .
pytest
```
Tests use fake adapters and an in-memory store, so they need no API key, database or
model download.

## Commands

| Command | Branch | What it does |
| --- | --- | --- |
| `python -m app.cli info` | both | Show the active configuration (no secrets) |
| `python -m app.cli ingest` | both | Index `content/`; next runs only touch changed files |
| `python -m app.cli ask "..."` | both | Ask a question (`--stage`, `--sector`; `rag-pipeline` also `--business-id`, `--location`) |
| `python -m app.cli eval` | both | Retrieval quality (`dev0`: hit rate, `--no-answers` for free runs; `rag-pipeline`: hit rate at 3 and MRR) |
| `python -m app.cli serve` | dev0 | API at http://127.0.0.1:8000/docs |
| `python -m app.cli feedback` | dev0 | Latest thumbs up/down |
| `uvicorn app.main:app --port 8100` | rag-pipeline | Run the API |
| `python -m app.cli init-db` | rag-pipeline | Create the Oracle table and indexes |
| `python -m app.cli backup` / `restore` | rag-pipeline | Export or reload all chunks and vectors (JSONL) |

## HTTP API

| Method | Path | Branch | What it does |
| --- | --- | --- | --- |
| POST | `/chat` | dev0 | `{"question", "user_context": {"stage", "sector"}}` → `{"answer", "sources"}` |
| POST | `/chat/stream` | dev0 | Same body; server-sent events `sources`, `token`..., `done` |
| POST | `/feedback` | dev0 | `{"question", "answer", "sources", "rating": "up"\|"down", "comment"}` |
| POST | `/ask` | rag-pipeline | `{"question", "profile": {"business_id", "sector", "founder_stage", "location"}}` → answer, sources, citations |
| POST | `/businesses/{id}/documents` | rag-pipeline | Upload a founder's private file |
| DELETE | `/businesses/{id}/documents/{name}` | rag-pipeline | Delete that file and its vectors |
| GET | `/health` | both | Status check |

On `rag-pipeline`, every call needs an `X-API-Key` header when `SERVICE_API_KEY` is set.

## Adding content

Put files in `content/<folder>/`. The folder sets the type when the file doesn't:

| Folder | Type |
| --- | --- |
| `stories` | story (founder experiences) |
| `frameworks` | framework |
| `case-studies` | case_study |
| `faq` | faq |
| `insights`, `datasets`, `schemes`, `market-reports` | rag-pipeline only |

Markdown files use frontmatter:
```
---
title: "BHUMI: positioning and pitch"
type: case_study        # story | framework | case_study | faq
people: [Sara]
founder_stage: early    # idea | early | traction
sector: social-impact
topics: [positioning, pitch]
date: 2026-05
visibility: public      # public | internal (internal is never indexed)
---
```

On `rag-pipeline`, PDF, DOCX, TXT and CSV files (max 10 MB) take the same fields from a
sidecar file named `<file name>.meta.yaml`. Market reports also need `publisher` and
`publication_year`.

The four files in `content/` today are **samples**. Replace them with real content written
or confirmed by Disha's founders.

## Project layout

```
app/core/        config, ports (interfaces), container (wiring), logging
app/adapters/    concrete implementations: vector stores, embedders, LLMs, loaders, fakes
app/features/    one folder per feature: ingestion, retrieval, chat, evaluation,
                 feedback (dev0), backup (rag-pipeline)
content/         the knowledge: stories, frameworks, case studies, FAQs
docs/            decisions.md, deploy.md (dev0), rag-pipeline.md (rag-pipeline)
tests/           mirrors app/, runs offline with fake adapters
```

## Architecture rules

- **Vertical slices:** each feature lives in `app/features/<name>/` and talks to other
  features only through their `service.py`.
- **Ports and adapters:** outside services are interfaces in `app/core/ports.py`. Config
  alone picks the implementation, so swapping a store or model needs no code change.
- **Config only through `app/core/config.py`**, no hard-coded values.
- **Secrets** come from `.env` or environment variables only and are never logged or committed.
- **Record design choices** in `docs/decisions.md`.
- `ruff check .` and `pytest` must pass before a merge.

## Documentation

- `docs/decisions.md`: every design decision and why
- `docs/deploy.md` (dev0): Docker, Render and Railway steps, what data must persist
- `docs/rag-pipeline.md` (rag-pipeline): ingestion and answering, step by step, with diagrams
- `CLAUDE.md`: working rules for AI coding assistants on this repo

## Status and next steps

- [x] Skeleton, ingestion, retrieval, chat, evaluation (both branches)
- [x] Streaming chat, feedback, deploy guide (`dev0`)
- [x] Zero-budget stack, file uploads, hybrid search and reranking, backups (`rag-pipeline`)
- [ ] Replace the sample content with real Disha content
- [ ] Choose one stack and merge the branches
- [ ] Write 20 to 50 real founder test questions and tune retrieval with `eval`
