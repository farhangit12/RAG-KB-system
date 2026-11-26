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
