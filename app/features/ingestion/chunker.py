"""Split markdown into chunks: first by headings, then by paragraphs, ~``size`` chars.

Each chunk starts with its heading path (e.g. "The Disha Path > 2. Talk to ten real
people") so the chunk keeps its context when retrieved alone. Consecutive chunks of the
same section share a small ``overlap`` of text.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class TextPiece:
    """One chunk of text and the heading path it sits under."""

    heading: str
    text: str


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return ``(heading_path, body)`` pairs, in document order."""
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    body: list[str] = []

    def flush() -> None:
        content = "\n".join(body).strip()
        if content:
            sections.append((" > ".join(h for _, h in stack), content))
        body.clear()

    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        match = None if in_code else _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            stack[:] = [(lvl, h) for lvl, h in stack if lvl < level]
            stack.append((level, match.group(2)))
        else:
            body.append(line)
    flush()
    return sections


def _split_long(paragraph: str, size: int) -> list[str]:
    """Break a paragraph longer than ``size`` at sentence ends, then at words."""
    if len(paragraph) <= size:
        return [paragraph]
    parts: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        for piece in textwrap.wrap(sentence, size) if len(sentence) > size else [sentence]:
            if current and len(current) + 1 + len(piece) > size:
                parts.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
    if current:
        parts.append(current)
    return parts


def _tail(text: str, n: int) -> str:
    """Last ~``n`` characters of ``text``, starting at a word boundary."""
    if n <= 0:
        return ""
    if len(text) <= n:
        return text
    tail = text[-n:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail


def _pack(paragraphs: list[str], size: int, overlap: int) -> list[str]:
    units = [u for p in paragraphs for u in _split_long(p, size)]
    chunks: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + 2 + len(unit) > size:
            chunks.append(current)
            carry = _tail(current, overlap)
            current = f"{carry}\n\n{unit}" if carry else unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(text: str, size: int = 800, overlap: int = 100) -> list[TextPiece]:
    """Chunk a markdown body (frontmatter already removed)."""
    pieces: list[TextPiece] = []
    for heading, body in split_sections(text):
        paragraphs = [p.strip() for p in _PARAGRAPH_BREAK.split(body) if p.strip()]
        for chunk_body in _pack(paragraphs, size, overlap):
            full = f"{heading}\n\n{chunk_body}" if heading else chunk_body
            pieces.append(TextPiece(heading=heading, text=full))
    return pieces
