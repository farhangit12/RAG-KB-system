"""Command line interface. Run ``python -m app.cli --help``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from app.core.config import get_settings
from app.core.container import Container, build_container
from app.core.logging import configure_logging
from app.core.ports import LLMError
from app.features.chat import service as chat
from app.features.evaluation import service as evaluation
from app.features.feedback import service as feedback_service
from app.features.ingestion import service as ingestion
from app.features.retrieval.service import QueryFilters

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


Many = Annotated[list[str] | None, typer.Option()]


@app.command()
def ingest(
    rebuild: Annotated[bool, typer.Option(help="Re-embed everything from scratch.")] = False,
) -> None:
    """Index the content folder. Only new or changed files are re-embedded."""
    r = ingestion.ingest(_container(), rebuild=rebuild)
    if r.rebuilt:
        typer.echo("full rebuild")
    typer.echo(
        f"added {len(r.added)}, updated {len(r.updated)}, unchanged {len(r.unchanged)}, "
        f"removed {len(r.removed)}; {r.chunks_written} chunks written"
    )
    for label, items in (("added", r.added), ("updated", r.updated), ("removed", r.removed)):
        for item in items:
            typer.echo(f"  {label}: {item}")
    if r.skipped_internal:
        typer.echo(f"skipped internal: {', '.join(r.skipped_internal)}")


@app.command()
def ask(
    question: str,
    type_: Annotated[
        list[str] | None, typer.Option("--type", help="story | framework | case_study | faq")
    ] = None,
    stage: Annotated[list[str] | None, typer.Option(help="idea | early | traction")] = None,
    sector: Many = None,
    person: Annotated[list[str] | None, typer.Option(help="e.g. Sara")] = None,
    topic: Many = None,
) -> None:
    """Ask a question and print a cited answer. Filters are optional and repeatable."""
    filters = QueryFilters(
        type=type_ or [],
        stage=stage or [],
        sector=sector or [],
        people=person or [],
        topics=topic or [],
    )
    try:
        result = chat.answer(_container(), question, filters=filters)
    except LLMError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(result.text)
    typer.echo("\nSources:")
    for ref in result.sources:
        typer.echo(f"  - [{ref.title}] ({ref.source}, score {ref.score:.2f})")


@app.command("eval")
def evaluate(
    answers: Annotated[
        bool, typer.Option(help="Also generate answers with the LLM (costs API calls).")
    ] = True,
    questions: Annotated[Path | None, typer.Option(help="Questions YAML file.")] = None,
    out: Annotated[Path | None, typer.Option(help="Folder for the report.")] = None,
) -> None:
    """Run the test questions, print retrieval hit rates and save a markdown report."""
    report = evaluation.run_eval(_container(), questions, with_answers=answers, out_dir=out)
    for r in report.results:
        rate = "n/a " if r.hit_rate is None else f"{r.hit_rate:4.0%}"
        flag = " (error)" if r.error else ""
        typer.echo(f"{rate}  {r.item.id}{flag}")
    mean = report.mean_hit_rate
    typer.echo(f"mean hit rate: {'n/a' if mean is None else f'{mean:.0%}'}")
    typer.echo(f"report: {report.report_path}")


@app.command()
def feedback(limit: Annotated[int, typer.Option(help="How many to show.")] = 20) -> None:
    """Show the most recent feedback, newest first."""
    repo = feedback_service.build_repository(get_settings())
    for r in feedback_service.recent(repo, limit):
        icon = "+" if r.rating == "up" else "-"
        typer.echo(f"[{icon}] #{r.id} {r.created_at}  {r.question}")
        if r.comment:
            typer.echo(f"      comment: {r.comment}")


@app.command()
def serve(reload: Annotated[bool, typer.Option(help="Restart on code changes.")] = False) -> None:
    """Run the HTTP API (host/port from HOST and PORT settings)."""
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:create_app", factory=True, host=s.host, port=s.port, reload=reload)


if __name__ == "__main__":
    app()
