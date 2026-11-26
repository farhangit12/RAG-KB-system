from __future__ import annotations

from app.features.ingestion.chunker import chunk_markdown, split_sections

DOC = """# Guide

Intro paragraph.

## Step one

First step text.

### Detail

Deeper text.

## Step two

Second step text.
"""


def test_sections_keep_heading_path() -> None:
    headings = [h for h, _ in split_sections(DOC)]
    assert headings == [
        "Guide",
        "Guide > Step one",
        "Guide > Step one > Detail",
        "Guide > Step two",
    ]


def test_heading_inside_code_block_is_not_a_heading() -> None:
    text = "# Real\n\n```\n# not a heading\n```\n"
    assert [h for h, _ in split_sections(text)] == ["Real"]


def test_chunks_start_with_heading() -> None:
    pieces = chunk_markdown(DOC)
    assert pieces[1].text.startswith("Guide > Step one\n\nFirst step text.")


def test_long_sections_split_near_size_with_overlap() -> None:
    para = " ".join(f"Sentence number {i} is here." for i in range(60))
    text = "# Long\n\n" + "\n\n".join([para, para])
    pieces = chunk_markdown(text, size=300, overlap=50)
    assert len(pieces) > 3
    bodies = [p.text.removeprefix("Long\n\n") for p in pieces]
    assert all(len(b) <= 300 + 50 + 2 for b in bodies)
    # overlap: the start of each later chunk repeats the end of the previous one
    first_tail_word = bodies[0].split()[-1]
    assert first_tail_word in bodies[1][:80]


def test_no_overlap_when_zero() -> None:
    text = "# A\n\n" + "\n\n".join(["word " * 50] * 4)
    pieces = chunk_markdown(text, size=300, overlap=0)
    assert all(p.text.count("word") <= 60 for p in pieces)


def test_empty_text_gives_no_chunks() -> None:
    assert chunk_markdown("") == []
