"""Retrieval evaluation: run test questions and measure hit rate at k and MRR.

The test file is YAML, written by Disha from real founder questions::

    - question: "Which seed fund schemes can an early-stage startup apply for?"
      expected_sources: ["schemes/seed-fund.pdf"]
    - question: "How should I price my first product?"
      expected_sources: ["frameworks/disha-path.md"]
      business_id: demo-business     # optional: also searches that business's files

Re-run after every change to chunking, models, filters or thresholds.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.core.container import Container
from app.features.evaluation.models import CaseResult, EvalCase, EvalReport
from app.features.retrieval import service as retrieval


def load_cases(path: Path) -> list[EvalCase]:
    """Read and check the YAML test file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    cases = []
    for i, item in enumerate(raw, start=1):
        if not item.get("question") or not item.get("expected_sources"):
            raise ValueError(f"case {i}: needs question and expected_sources")
        cases.append(
            EvalCase(item["question"], tuple(item["expected_sources"]), item.get("business_id"))
        )
    return cases


def evaluate(container: Container, cases: list[EvalCase], k: int | None = None) -> EvalReport:
    """Rank chunks for every case (after reranking) and score where the right source lands."""
    k = k or container.settings.rerank_keep
    report = EvalReport(k=k)
    for case in cases:
        profile = retrieval.BusinessProfile(case.business_id) if case.business_id else None
        result = retrieval.retrieve(container, case.question, profile)
        got = [c.chunk.source for c in result.ranked]
        rank = next((i for i, s in enumerate(got, start=1) if s in case.expected_sources), None)
        report.cases.append(CaseResult(case.question, case.expected_sources, got[:k], rank))
    return report
