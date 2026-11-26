# Deploying the Disha RAG API

The API runs as one long-lived Docker container. **Don't use Vercel serverless for it.**
Serverless functions have no persistent disk and restart cold, so the vector index and the
feedback database would be lost, and the embedding model would reload on every cold start.
The Disha website can stay on Vercel and call this API.

## What needs to persist

| Data | Where | Persist? |
|---|---|---|
| Vector index (Chroma) | `/app/data/chroma` | Nice to have. Without a disk it is rebuilt from `content/` at every start (seconds for a small knowledge base). |
| Manifest | `/app/data/manifest-*.json` | Same as above. |
| Feedback (SQLite) | `/app/data/feedback.db` | **Yes**, or you lose ratings on every deploy. |

So: mount a persistent disk/volume at **`/app/data`**.

> **Cost note:** persistent disks are a paid feature on Render (they need a paid instance
> type). Railway volumes are billed by usage. Check current pricing before you turn either
> on. Without a disk, everything works except that feedback is wiped on each redeploy.

## Environment variables

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your key (mark it secret) |
| `CORS_ORIGINS` | `["https://disha-advisory-vert.vercel.app"]` |
| `TRUST_PROXY_HEADERS` | `true` (already set in the Dockerfile) |
| `PORT` | set automatically by Render/Railway; the app reads it |

Every other setting has a sensible default (see `.env.example`).

## Render

1. Push the repo to GitHub.
2. Render dashboard -> **New -> Web Service** -> connect the repo and pick the branch.
3. **Runtime / Language:** Docker (Render detects the `Dockerfile`).
4. **Health check path:** `/health`.
5. **Environment:** add the variables above.
6. Optional (paid): **Disks -> Add disk**, mount path `/app/data`, 1 GB is plenty.
7. Deploy. Check `https://<your-service>.onrender.com/health` returns `{"status":"ok"}`.

## Railway

1. Railway dashboard -> **New Project -> Deploy from GitHub repo** -> pick the repo.
   Railway builds the `Dockerfile` automatically.
2. **Variables:** add the variables above.
3. **Settings -> Networking -> Generate Domain** to get a public URL.
4. Optional: right-click the service -> **Attach Volume**, mount path `/app/data`.
5. Check `https://<your-app>.up.railway.app/health`.

## Updating content

Edit files in `content/`, commit, and push. The new image runs `python -m app.cli ingest`
on start: only changed files are re-embedded and deleted files are removed.

## Calling it from the Disha website

```js
const res = await fetch("https://<your-api>/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: "How do I find my first customer?",
    user_context: { stage: "idea", sector: "edtech" },
  }),
});
const { answer, sources } = await res.json();
```

For live typing, use `POST /chat/stream` and read the `sources`, `token` and `done`
server-sent events.

## Swapping Chroma for Qdrant (config only)

1. Build with the extra: `docker build --build-arg EXTRAS="[qdrant]" -t disha-rag .`
   (locally: `pip install -e ".[qdrant]"`).
2. Set `VECTOR_STORE=qdrant` and either:
   - `QDRANT_URL=https://<cluster>.cloud.qdrant.io` + `QDRANT_API_KEY=...` (a hosted Qdrant
     server; Qdrant Cloud has a free tier but check its limits), or
   - leave `QDRANT_URL` empty for embedded local files in `/app/data/qdrant`.
3. Restart. The settings fingerprint changed, so the first `ingest` rebuilds the index
   automatically.

No feature code changes. `tests/test_swap_by_config.py` runs the full pipeline on Memory,
Chroma and Qdrant to prove it.

## Running several instances

The API keeps no session state, so you can run several copies behind a load balancer.
Before you do:
- move the rate limiter to a shared store (add a Redis adapter behind the `RateLimiter`
  port), otherwise each copy counts separately;
- use a server vector store (Qdrant server) and a server database for feedback (a
  Postgres repository behind `FeedbackRepository`), since local files aren't shared.
