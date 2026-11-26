"""Render an evaluation run as a markdown report for a human to read."""

from __future__ import annotations

from datetime import datetime

from app.features.evaluation.models import EvalReport, QuestionResult


def _rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _section(r: QuestionResult) -> list[str]:
    q = r.item
    ctx = ", ".join(f"{k}: {v}" for k, v in (("stage", q.stage), ("sector", q.sector)) if v)
    lines = [
        f"## {q.id}",
        "",
        f"**Question:** {q.question}",
        "",
        f"- Context: {ctx or 'none'}",
        f"- Expected: {', '.join(q.expected_sources) or '(none; not covered)'}",
        f"- Retrieved: {', '.join(r.retrieved) or '(nothing)'}",
        f"- Hit rate: {_rate(r.hit_rate)}",
    ]
    if q.notes:
        lines.append(f"- Notes: {q.notes}")
    lines.append("")
    if r.error:
        lines += [f"**Error:** {r.error}", ""]
    elif r.answer is not None:
        lines += ["### Answer", "", r.answer, ""]
    return lines


def render(report: EvalReport, when: datetime) -> str:
    """Return the full markdown text."""
    lines = [
        f"# Disha RAG evaluation, {when:%Y-%m-%d %H:%M}",
        "",
        f"**Mean retrieval hit rate:** {_rate(report.mean_hit_rate)}",
        "",
        "| id | hit rate | expected | retrieved |",
        "|---|---|---|---|",
    ]
    for r in report.results:
        lines.append(
            f"| {r.item.id} | {_rate(r.hit_rate)} | {', '.join(r.item.expected_sources) or '-'} "
            f"| {', '.join(r.retrieved) or '-'} |"
        )
    lines.append("")
    for r in report.results:
        lines += _section(r)
    return "\n".join(lines)
