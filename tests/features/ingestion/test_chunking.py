from __future__ import annotations

from app.adapters.tokenizers.estimate import EstimateTokenCounter
from app.features.ingestion.chunking import chunk_markdown

COUNT = EstimateTokenCounter()


def _sentences(n: int, word: str = "growth") -> str:
    return " ".join(f"Sentence {i} talks about {word} plans for founders." for i in range(n))


def test_small_document_is_one_chunk() -> None:
    pieces = chunk_markdown("# Title\n\nShort text.", COUNT, 500, 75)
    assert len(pieces) == 1
    assert pieces[0].section == "Title"


def test_every_chunk_is_within_the_limit_and_overlaps() -> None:
    text = "# Market\n\n" + _sentences(200)
    pieces = chunk_markdown(text, COUNT, 500, 75)
    assert len(pieces) > 3
    assert all(p.tokens <= 500 for p in pieces)
    # neighbours share text (overlap)
    last_sentence = pieces[0].text.splitlines()[-1]
    assert last_sentence in pieces[1].text
    assert all(p.text.startswith(("# Market", "[Section: Market]")) for p in pieces)


def test_table_stays_whole_or_splits_with_header() -> None:
    rows = "\n".join(f"| City {i} | ₹{i}00 |" for i in range(300))
    table = "| City | Price |\n|---|---|\n" + rows
    pieces = chunk_markdown("# Prices\n\nIntro text here.\n\n" + table, COUNT, 500, 75)
    table_pieces = [p for p in pieces if "| City | Price |" in p.text]
    assert len(table_pieces) > 1
    assert all("|---|---|" in p.text for p in table_pieces)
    assert all(p.tokens <= 500 for p in pieces)


def test_page_numbers_follow_markers() -> None:
    text = (
        "<!-- page: 1 -->\n\n" + _sentences(60)
        + "\n\n<!-- page: 2 -->\n\n" + _sentences(60, "pricing")
    )
    pieces = chunk_markdown(text, COUNT, 500, 75)
    assert pieces[0].page_start == 1
    assert pieces[-1].page_end == 2


def test_sections_follow_heading_levels() -> None:
    text = "# A\n\n## B\n\n" + _sentences(80) + "\n\n# C\n\n" + _sentences(80)
    sections = {p.section for p in chunk_markdown(text, COUNT, 500, 75)}
    assert "A > B" in sections
    assert "C" in sections
