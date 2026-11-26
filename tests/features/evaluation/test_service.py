from __future__ import annotations

from pathlib import Path

import pytest

from app.core.container import Container
from app.core.ports import Chunk
from app.features.evaluation.service import evaluate, load_cases


def test_hit_rate_and_mrr(container: Container, tmp_path: Path) -> None:
    for cid, text in [("pricing.md#0", "how to price your first product"),
                      ("hiring.md#0", "how to hire your first employee")]:
        chunk = Chunk(cid, cid.split("#")[0], text, {"visibility": "public"})
        container.vector_store.upsert([chunk], container.embedder.embed([text]))
    cases_file = tmp_path / "cases.yaml"
    cases_file.write_text(
        "- question: price first product\n  expected_sources: [pricing.md]\n"
        "- question: hire first employee\n  expected_sources: [hiring.md]\n"
        "- question: tax filing deadlines\n  expected_sources: [tax.md]\n",
        encoding="utf-8",
    )
    report = evaluate(container, load_cases(cases_file), k=3)
    assert [c.rank for c in report.cases] == [1, 1, None]
    assert report.hit_rate == pytest.approx(2 / 3)
    assert report.mrr == pytest.approx(2 / 3)


def test_bad_case_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- question: no expected\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected_sources"):
        load_cases(bad)
