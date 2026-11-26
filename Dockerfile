# Disha RAG API. Build:  docker build -t disha-rag .
# Run:    docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... -v disha-data:/app/data disha-rag
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Optional extras, e.g. --build-arg EXTRAS="[qdrant]"
ARG EXTRAS=""

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install ".${EXTRAS}"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser /app
USER appuser

# Download the local embedding model at build time so cold starts are fast.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as D; D()(['warm up'])"

COPY --chown=appuser content ./content
COPY --chown=appuser eval ./eval

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/app/data \
    LOG_JSON=true \
    TRUST_PROXY_HEADERS=true

EXPOSE 8000

# Incremental ingest on every start (only changed files are re-embedded), then serve.
CMD ["sh", "-c", "python -m app.cli ingest && python -m app.cli serve"]
