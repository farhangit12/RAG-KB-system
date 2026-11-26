# Disha RAG knowledge base

An assistant that answers questions from students and first-time founders using
[Disha](https://disha-advisory-vert.vercel.app)'s own stories, frameworks, case studies,
FAQs, schemes, datasets and market reports, with citations.

Runs at zero cost: Oracle Always Free for storage and vector search, local open-source
models for embeddings and reranking, and Groq's free plan for answers
(see `docs/decisions.md`, 007).

## How it works
```
file -> validate -> load -> clean -> chunk (500 tokens, 75 overlap) -> embed (bge-m3) -> Oracle
question -> hybrid search -> filter -> fuse -> rerank -> top 3 -> pack -> Groq -> check citations
```
Full diagrams and rules: [`docs/rag-pipeline.md`](docs/rag-pipeline.md).

## Setup (Windows PowerShell)
```
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"            # enough for tests (fake adapters)
python -m pip install -e ".[dev,all]"        # production: Oracle, local models, Docling
copy .env.example .env
```
Open `.env` and set `GROQ_API_KEY`, the `ORACLE_*` values and `SERVICE_API_KEY`.

## Check it works
```
python -m app.cli info
ruff check .
pytest
```
Tests use fake adapters and an in-memory store: no API key, no database, no model download.

## Use it
```
python -m app.cli init-db                      # once: create the Oracle table and indexes
python -m app.cli ingest                       # index content/ (only new or changed files)
python -m app.cli ask "Which grants can an early-stage startup apply for?" --sector edtech
python -m app.cli eval eval/questions.example.yaml   # hit rate at 3 and MRR
python -m app.cli backup                       # JSONL export for Account 4 Object Storage
uvicorn app.main:app --port 8100               # HTTP API
```

### HTTP API (every call needs `X-API-Key` when `SERVICE_API_KEY` is set)
| Method | Path | What it does |
| --- | --- | --- |
| POST | `/ask` | `{"question": ..., "profile": {"business_id", "sector", "founder_stage", "location", ...}}` -> answer, sources, citations |
| POST | `/businesses/{id}/documents` | Upload a founder's private file (form field `file`, optional `title`) |
| DELETE | `/businesses/{id}/documents/{name}` | Delete that file, its chunks and vectors |
| GET | `/health` | Status and chunk count |

## Adding content
Put files in `content/<folder>/`. The folder sets the type when it is not given:

| Folder | Type |
| --- | --- |
| `stories` | story (founder experiences) |
| `frameworks` | framework |
| `case-studies` | case_study |
| `faq` | faq |
| `insights` | insight (consulting insights) |
| `datasets` | dataset |
| `schemes` | scheme (government schemes) |
| `market-reports` | market_report |

Markdown files use frontmatter:
```
---
title: "BHUMI: positioning and pitch"
type: case_study        # optional when the folder says it
people: [Sara]
founder_stage: early
sector: social-impact   # "industry" also accepted
location: rajasthan     # optional; "all" matches everyone
topics: [positioning, pitch]
date: 2026-05
visibility: public      # public | internal (never indexed)
---
```
PDF, DOCX, TXT and CSV files take the same fields from a sidecar file named
`<file name>.meta.yaml`, for example `market-reports/edtech-2025.pdf.meta.yaml`:
```
title: "EdTech market in India"
publisher: "[Publisher]"      # required for market reports
publication_year: 2025        # required for market reports
sector: edtech
valid_until: 2027-03-31       # optional: stop using it after this date
```
Max 10 MB per file. The four markdown files in `content/` now are **samples**: replace them
with real content. Never invent Disha content, client outcomes, numbers or quotes.

## Layout
- `app/core/`: config, ports (interfaces), container (wiring), logging, text helpers
- `app/adapters/`: embedders (bge_m3, fake), rerankers (bge, fake), llms (groq, fake),
  vectorstores (oracle, chroma, memory), loaders (auto, markdown, files), tokenizers
- `app/features/`: `ingestion`, `retrieval`, `chat`, `evaluation`, `backup`
- `sql/oracle/`: KB table and indexes
- `docs/decisions.md`: why things are built the way they are
- `docs/rag-pipeline.md`: the pipeline step by step
