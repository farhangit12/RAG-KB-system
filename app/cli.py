"""Command line interface. Run ``python -m app.cli --help``."""

from __future__ import annotations

import typer

from app.core.config import get_settings
from app.core.container import Container, build_container
from app.core.logging import configure_logging
from app.core.ports import LLMError
from app.features.chat import service as chat
from app.features.ingestion import service as ingestion

app = typer.Typer(help="Disha RAG knowledge assistant.", no_args_is_help=True)


def _container() -> Container:
    return build_container(get_settings())


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
    typer.echo(f"embedder:       {s.embedder}")
    typer.echo(f"llm:            {s.llm} ({s.anthropic_model})")
    typer.echo(f"loader:         {s.loader}")
    typer.echo(f"api key set:    {'yes' if s.anthropic_api_key else 'no'}")
    typer.echo(f"content_dir:    {s.content_dir} ({len(content_files)} markdown files)")
    typer.echo(f"data_dir:       {s.data_dir}")


@app.command()
def ingest() -> None:
    """Index the content folder into the vector store."""
    report = ingestion.ingest(_container())
    typer.echo(f"indexed {len(report.added)} files, {report.chunks_written} chunks")
    if report.skipped_internal:
        typer.echo(f"skipped internal: {', '.join(report.skipped_internal)}")


@app.command()
def ask(question: str) -> None:
    """Ask a question and print a cited answer."""
    try:
        result = chat.answer(_container(), question)
    except LLMError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(result.text)
    typer.echo("\nSources:")
    for ref in result.sources:
        typer.echo(f"  - [{ref.title}] ({ref.source}, score {ref.score:.2f})")


if __name__ == "__main__":
    app()
