"""Command line interface. Run ``python -m app.cli --help``."""

from __future__ import annotations

import typer

from app.core.config import get_settings
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
    typer.echo(f"embedder:       {s.embedder}")
    typer.echo(f"llm:            {s.llm} ({s.anthropic_model})")
    typer.echo(f"loader:         {s.loader}")
    typer.echo(f"api key set:    {'yes' if s.anthropic_api_key else 'no'}")
    typer.echo(f"content_dir:    {s.content_dir} ({len(content_files)} markdown files)")
    typer.echo(f"data_dir:       {s.data_dir}")


if __name__ == "__main__":
    app()
