"""Command line interface. Run ``python -m app.cli --help``."""

from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import get_settings
from app.core.container import build_container
from app.core.logging import configure_logging

app = typer.Typer(help="Disha RAG knowledge assistant.", no_args_is_help=True)


@app.callback()
def _setup() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)


@app.command()
def info() -> None:
    """Show the active configuration (secrets are never printed)."""
    s = get_settings()
    content_files = sorted(s.content_dir.rglob("*.md")) if s.content_dir.exists() else []
    typer.echo(f"app:            {s.app_name}")
    typer.echo(f"vector_store:   {s.vector_store}")
    typer.echo(f"embedder:       {s.embedder} ({s.embed_model})")
    typer.echo(f"reranker:       {s.reranker} ({s.rerank_model})")
    typer.echo(f"llm:            {s.llm} ({s.groq_model})")
    typer.echo(f"loader:         {s.loader}")
    typer.echo(f"tokenizer:      {s.tokenizer}")
    typer.echo(f"api key set:    {'yes' if s.groq_api_key else 'no'}")
    typer.echo(f"chunking:       {s.chunk_size} tokens, {s.chunk_overlap} overlap")
    typer.echo(f"content_dir:    {s.content_dir} ({len(content_files)} markdown files)")
    typer.echo(f"data_dir:       {s.data_dir}")


@app.command("init-db")
def init_db() -> None:
    """Create the Oracle KB table and indexes (safe to run twice)."""
    store = build_container().vector_store
    if not hasattr(store, "create_schema"):
        typer.echo("The configured vector store needs no schema.")
        return
    store.create_schema()
    typer.echo("Schema ready.")


@app.command()
def ingest() -> None:
    """Index CONTENT_DIR: new and changed files are indexed, deleted files removed."""
    from app.features.ingestion import service

    report = service.ingest_content(build_container())
    for status in ("indexed", "unchanged", "duplicate", "internal", "removed", "failed"):
        typer.echo(f"{status:<10} {report.count(status)}")
    typer.echo(f"chunks     {report.chunks}")
    for r in report.failed:
        typer.echo(f"  FAILED {r.source}: {r.error}", err=True)
    if report.failed:
        raise typer.Exit(code=1)


@app.command()
def ask(
    question: str,
    business_id: str | None = typer.Option(None, help="Also search this business's files"),
    sector: str | None = None,
    stage: str | None = None,
    location: str | None = None,
) -> None:
    """Ask a question and print the answer with its sources."""
    from app.features.chat import service
    from app.features.retrieval.service import BusinessProfile

    profile = None
    if business_id or sector or stage or location:
        profile = BusinessProfile(business_id or "", sector, stage, location)
    result = service.answer(build_container(), question, profile)
    typer.echo(result.answer)
    if result.sources:
        typer.echo("\nSources:")
        for s in result.sources:
            mark = "*" if s.label in result.cited else " "
            typer.echo(f" {mark}[{s.label}] {s.citation}  ({s.source}, score {s.score:.2f})")
    if result.low_confidence:
        typer.echo("\n(low confidence: the answer cited no sources)", err=True)


@app.command("eval")
def eval_cmd(
    cases_file: Path = typer.Argument(..., help="YAML file of test questions"),
    k: int = typer.Option(3, help="Count a hit when the right source is in the top k"),
) -> None:
    """Measure retrieval: hit rate at k and MRR."""
    from app.features.evaluation import service

    container = build_container()
    report = service.evaluate(container, service.load_cases(cases_file), k)
    for c in report.cases:
        status = f"rank {c.rank}" if c.rank else "MISS"
        typer.echo(f"{status:<8} {c.question}")
    typer.echo(f"\nhit@{report.k}: {report.hit_rate:.2f}   MRR: {report.mrr:.2f}   "
               f"({len(report.cases)} questions)")


@app.command()
def backup(out_dir: Path | None = None) -> None:
    """Export all chunks and vectors to a .jsonl.gz file."""
    from app.features.backup import service

    typer.echo(service.export_jsonl(build_container(), out_dir))


@app.command()
def restore(path: Path) -> None:
    """Load a backup file into the configured store."""
    from app.features.backup import service

    typer.echo(f"restored {service.restore_jsonl(build_container(), path)} chunks")


if __name__ == "__main__":
    app()
