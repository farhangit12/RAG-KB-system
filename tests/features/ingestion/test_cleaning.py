from __future__ import annotations

from app.features.ingestion.cleaning import clean_markdown


def test_removes_blank_lines_spaces_and_control_chars() -> None:
    raw = "Hello   world\x00 ​\n\n\n\nSecond    para."
    assert clean_markdown(raw) == "Hello world\n\nSecond para."


def test_joins_broken_lines_and_hyphenated_words() -> None:
    raw = "The market for kulhad tea is grow-\ning in tier two\ncities across India."
    expected = "The market for kulhad tea is growing in tier two cities across India."
    assert clean_markdown(raw) == expected


def test_keeps_lists_headings_tables_currency_and_dates() -> None:
    raw = (
        "# Pricing\n\n- Price: ₹999\n- Launch: 2026-01-15\n\n"
        "| Plan | Price |\n|---|---|\n| Starter | ₹999 |"
    )
    out = clean_markdown(raw)
    assert "# Pricing" in out
    assert "- Price: ₹999\n- Launch: 2026-01-15" in out
    assert "| Starter | ₹999 |" in out


def test_drops_repeated_headers_footers_and_page_numbers() -> None:
    pages = []
    for n in range(1, 5):
        pages.append(f"<!-- page: {n} -->\n\nDisha Report 2026\n\nBody text {n} here.\n\n{n}")
    out = clean_markdown("\n\n".join(pages))
    assert "Disha Report 2026" not in out
    assert "Body text 3 here." in out
    assert "\n\n2\n\n" not in out
    assert "<!-- page: 3 -->" in out


def test_removes_duplicate_paragraphs() -> None:
    raw = "Same paragraph.\n\nOther.\n\nsame   PARAGRAPH."
    assert clean_markdown(raw) == "Same paragraph.\n\nOther."
