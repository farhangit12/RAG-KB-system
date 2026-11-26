"""Public entry points for evaluation: ``load_questions`` and ``run_eval``."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from app.core.container import Container
from app.core.logging import get_logger
from app.core.ports import LLMError
from app.features.chat import service as chat
from app.features.evaluation.models import EvalQuestion, EvalReport, QuestionResult
from app.features.evaluation.report import render
from app.features.retrieval import service as retrieval

log = get_logger(__name__)

__all__ = ["EvalReport", "load_questions", "run_eval", "score"]


def load_questions(path: Path) -> list[EvalQuestion]:
    """Read and validate the questions file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    items = [EvalQuestion.model_validate(item) for item in raw]
    ids = [q.id for q in items]
    if len(ids) != len(set(ids)):
        raise ValueError("question ids must be unique")
    return items


def score(expected: list[str], retrieved: list[str]) -> float | None:
    """Share of expected sources found in ``retrieved`` (None if nothing is expected)."""
    if not expected:
        return None
    return sum(1 for s in expected if s in retrieved) / len(expected)


def _retrieved_sources(container: Container, q: EvalQuestion) -> list[str]:
    ctx = retrieval.UserContext(stage=q.stage, sector=q.sector)
    chunks = retrieval.retrieve(container, q.question, context=ctx)
    return list(dict.fromkeys(c.chunk.source for c in chunks))


def _evaluate_one(container: Container, q: EvalQuestion, with_answers: bool) -> QuestionResult:
    retrieved = _retrieved_sources(container, q)
    result = QuestionResult(q, retrieved, score(q.expected_sources, retrieved))
    if with_answers:
        ctx = retrieval.UserContext(stage=q.stage, sector=q.sector)
        try:
            result.answer = chat.answer(container, q.question, context=ctx).text
        except LLMError as e:
            result.error = str(e)
    return result


def run_eval(
    container: Container,
    questions_path: Path | None = None,
    with_answers: bool = True,
    out_dir: Path | None = None,
) -> EvalReport:
    """Run every question, then save a markdown report to ``out_dir`` (default REPORTS_DIR)."""
    s = container.settings
    questions = load_questions(questions_path or s.eval_questions_path)
    report = EvalReport([_evaluate_one(container, q, with_answers) for q in questions])
    when = datetime.now()
    target = out_dir or s.reports_dir
    target.mkdir(parents=True, exist_ok=True)
    report.report_path = target / f"eval-{when:%Y%m%d-%H%M%S}.md"
    report.report_path.write_text(render(report, when), encoding="utf-8")
    log.info("eval_done", extra={"questions": len(questions), "hit_rate": report.mean_hit_rate})
    return report
