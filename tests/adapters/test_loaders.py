from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.loaders.auto import build as build_auto
from app.adapters.loaders.files import csv_to_markdown, decode_bytes
from app.adapters.rerankers.fake import FakeReranker
from app.adapters.tokenizers.estimate import EstimateTokenCounter
from tests.conftest import write


def test_csv_blocks_repeat_the_header() -> None:
    data = ("a,b\n" + "\n".join(f"{i},{i}" for i in range(5))).encode()
    md = csv_to_markdown(data, rows_per_block=2)
    blocks = md.split("\n\n")
    assert len(blocks) == 3
    assert all(b.startswith("| a | b |\n|---|---|") for b in blocks)


def test_decode_handles_bom_and_windows_text() -> None:
    assert decode_bytes("﻿₹999".encode()) == "₹999"
    assert decode_bytes("caf\xe9".encode("cp1252")) == "café"


def test_auto_loader_reads_markdown_and_sidecars(settings, tmp_path: Path) -> None:
    loader = build_auto(settings)
    md = write(tmp_path / "faq" / "x.md", "---\ntitle: X\n---\nBody")
    [doc] = loader.load(md, tmp_path)
    assert (doc.source, doc.metadata["type"], doc.text) == ("faq/x.md", "faq", "Body")

    txt = write(tmp_path / "market-reports" / "r.txt", "Report body")
    meta = "publisher: IBEF\npublication_year: 2025\n"
    write(tmp_path / "market-reports" / "r.txt.meta.yaml", meta)
    [doc] = loader.load(txt, tmp_path)
    assert doc.metadata["type"] == "market_report"
    assert doc.metadata["publisher"] == "IBEF"

    with pytest.raises(ValueError, match="No loader"):
        loader.load(write(tmp_path / "x.xlsx", "x"), tmp_path)


def test_fake_reranker_and_estimate_tokenizer() -> None:
    assert FakeReranker().score("seed fund", ["seed fund scheme", "hiring"]) == [1.0, 0.0]
    assert EstimateTokenCounter().count("one two three") >= 3


def test_docx_fallback_keeps_headings_lists_and_tables(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    from app.adapters.loaders.files import docx_basic_to_markdown

    d = docx.Document()
    d.add_heading("Pricing", level=1)
    d.add_paragraph("Start with a test.")
    d.add_paragraph("Week one", style="List Bullet")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Plan", "Price"
    t.cell(1, 0).text, t.cell(1, 1).text = "Starter", "₹999"
    path = tmp_path / "p.docx"
    d.save(str(path))
    md = docx_basic_to_markdown(path)
    assert "## Pricing" in md
    assert "- Week one" in md
    assert "| Plan | Price |\n|---|---|\n| Starter | ₹999 |" in md


def test_pdf_fallback_adds_page_markers(tmp_path: Path) -> None:
    pytest.importorskip("pypdf")
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    from app.adapters.loaders.files import pdf_basic_to_markdown

    path = tmp_path / "r.pdf"
    c = canvas.Canvas(str(path))
    for n in (1, 2):
        c.drawString(72, 720, f"Page {n} text about seed funding.")
        c.showPage()
    c.save()
    md = pdf_basic_to_markdown(path)
    assert "<!-- page: 1 -->" in md and "<!-- page: 2 -->" in md
    assert "Page 2 text about seed funding." in md
