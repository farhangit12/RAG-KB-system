from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.container import Container
from app.core.ports import LLMError
from app.features.evaluation.service import load_questions, run_eval, score
from app.features.ingestion.service import ingest
from tests.conftest import REPO_ROOT

QUESTIONS = """
- id: dc
  question: "What is a Direction Call?"
  expected_sources: [faq/direction-call.md]
  notes: "mention the price"
- id: missing
  question: "What is a Direction Call?"
  expected_sources: [faq/direction-call.md, stories/nope.md]
- id: out-of-scope
  question: "Series A valuation?"
  expected_sources: []
"""


@pytest.fixture
def questions(tmp_path: Path) -> Path:
    p = tmp_path / "q.yaml"
    p.write_text(QUESTIONS, encoding="utf-8")
    return p


def test_score() -> None:
    assert score(["a", "b"], ["a", "c"]) == 0.5
    assert score([], ["a"]) is None


def test_repo_questions_file_is_valid() -> None:
    items = load_questions(REPO_ROOT / "eval" / "questions.yaml")
    assert len(items) >= 5
    for q in items:
        for src in q.expected_sources:
            assert (REPO_ROOT / "content" / src).exists(), src


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    p = tmp_path / "q.yaml"
    p.write_text("- {id: a, question: x}\n- {id: a, question: y}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_questions(p)


def test_run_eval_scores_and_writes_report(
    tmp_container: Container, questions: Path, tmp_path: Path
) -> None:
    ingest(tmp_container)
    report = run_eval(tmp_container, questions, out_dir=tmp_path / "reports")
    rates = {r.item.id: r.hit_rate for r in report.results}
    assert rates == {"dc": 1.0, "missing": 0.5, "out-of-scope": None}
    assert report.mean_hit_rate == 0.75
    text = report.report_path.read_text(encoding="utf-8")
    assert "**Mean retrieval hit rate:** 75%" in text
    assert "## dc" in text
    assert "FAKE ANSWER" in text
    assert "mention the price" in text


def test_run_eval_without_answers_makes_no_llm_calls(
    tmp_container: Container, questions: Path, tmp_path: Path
) -> None:
    ingest(tmp_container)
    report = run_eval(tmp_container, questions, with_answers=False, out_dir=tmp_path)
    assert tmp_container.llm.calls == []
    assert all(r.answer is None for r in report.results)


class _BrokenLLM:
    def generate(self, system: str, prompt: str) -> str:
        raise LLMError("down")

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        raise LLMError("down")


def test_llm_errors_are_recorded_not_fatal(
    tmp_container: Container, questions: Path, tmp_path: Path
) -> None:
    ingest(tmp_container)
    tmp_container.__dict__["llm"] = _BrokenLLM()
    report = run_eval(tmp_container, questions, out_dir=tmp_path)
    assert all(r.error == "down" for r in report.results)
    assert report.results[0].hit_rate == 1.0
