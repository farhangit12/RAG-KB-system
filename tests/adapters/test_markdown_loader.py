from __future__ import annotations

from pathlib import Path

from app.adapters.loaders.markdown_loader import MarkdownLoader


def test_reads_frontmatter_and_body(tmp_path: Path) -> None:
    f = tmp_path / "faq" / "q.md"
    f.parent.mkdir()
    f.write_text('---\ntitle: "Q"\ntype: faq\n---\n# Heading\n\nBody.', encoding="utf-8")
    [doc] = MarkdownLoader().load(f, tmp_path)
    assert doc.source == "faq/q.md"
    assert doc.metadata["title"] == "Q"
    assert doc.metadata["visibility"] == "public"
    assert "Body." in doc.text
    assert "title:" not in doc.text


def test_infers_type_and_title_without_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "case-studies" / "x.md"
    f.parent.mkdir()
    f.write_text("# Compass notes\n\nText.", encoding="utf-8")
    [doc] = MarkdownLoader().load(f, tmp_path)
    assert doc.metadata["type"] == "case_study"
    assert doc.metadata["title"] == "Compass notes"


def test_unknown_folder_and_no_heading_uses_file_name(tmp_path: Path) -> None:
    f = tmp_path / "misc.md"
    f.write_text("just text", encoding="utf-8")
    [doc] = MarkdownLoader().load(f, tmp_path)
    assert "type" not in doc.metadata
    assert doc.metadata["title"] == "misc"
