# Disha RAG knowledge base

An assistant that answers questions from students and first-time founders using
[Disha](https://disha-advisory-vert.vercel.app)'s own stories, frameworks, case studies
and FAQs, with citations.

## Setup (Windows PowerShell)
```
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```
Open `.env` and set `ANTHROPIC_API_KEY`.

## Check it works
```
python -m app.cli info
ruff check .
pytest
```

## Use it
```
python -m app.cli ingest                       # index content/ (only changed files next time)
python -m app.cli ask "Who should I talk to before I build?" --stage idea
python -m app.cli eval --no-answers            # retrieval hit rates, free
python -m app.cli eval                         # + answers in reports/ (uses the API)
python -m app.cli serve                        # API at http://127.0.0.1:8000/docs
python -m app.cli feedback                     # latest thumbs up/down
```
The first `ingest` downloads the local embedding model (~80 MB).

## API
- `POST /chat` `{"question": "...", "user_context": {"stage": "idea", "sector": "edtech"}}`
  -> `{"answer": "...", "sources": [{"title", "source", "type", "score"}]}`
- `POST /chat/stream`: same body; server-sent events `sources`, `token`..., `done`
- `POST /feedback` `{"question", "answer", "sources", "rating": "up"|"down", "comment"}`
- `GET /health`

Deploying: see [docs/deploy.md](docs/deploy.md).

## Adding content
Put markdown files in `content/stories`, `content/frameworks`, `content/case-studies`
or `content/faq`, with frontmatter like:
```
---
title: "BHUMI: positioning and pitch"
type: case_study        # story | framework | case_study | faq
people: [Sara]
founder_stage: early     # idea | early | traction
sector: social-impact
topics: [positioning, pitch]
date: 2026-05
visibility: public       # public | internal
---
```
The four files there now are **samples**: replace them with real content.

## Layout
- `app/core/`: config, ports (interfaces), container (wiring), logging
- `app/adapters/`: concrete implementations (Chroma, Anthropic, fakes, ...)
- `app/features/`: one folder per feature (ingestion, retrieval, chat, feedback, evaluation)
- `docs/decisions.md`: why things are built the way they are
