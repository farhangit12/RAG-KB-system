"""Structure-aware chunking, following the RAG design.

- Split by headings and paragraphs first.
- Pack sentences and list items into chunks of at most CHUNK_SIZE tokens (500).
- Overlap about CHUNK_OVERLAP tokens (75) between neighbours, so a new chunk every ~425.
- A document that fits in one chunk stays one chunk.
- A table stays whole; a table over the limit is split by rows with its header repeated.
- Each chunk starts with its section path, so it still makes sense when read alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.ports import TokenCounter
from app.features.ingestion.cleaning import PAGE_MARKER, split_paragraphs

_SENTENCE = re.compile(r"(?<=[.!?।])\s+")
_LIST = re.compile(r"^\s*([-*•]|\d+[.)])\s+")
_TABLE_RULE = re.compile(r"^\|?[\s:|-]+\|?$")
_PREFIX_ROOM = 40  # tokens kept free for the "[Section: ...]" line


@dataclass(frozen=True)
class Piece:
    """A chunk before it gets an id and metadata."""

    text: str
    tokens: int
    page_start: int | None
    page_end: int | None
    section: str | None


@dataclass
class _Unit:
    text: str
    tokens: int
    page: int | None
    section: str | None
    is_heading: bool = False


def _heading(line: str) -> tuple[int, str]:
    level = len(line) - len(line.lstrip("#"))
    return max(level, 1), line.lstrip("#").strip()


def _section(path: list[tuple[int, str]]) -> str | None:
    return " > ".join(t for _, t in path) or None


def chunk_markdown(text: str, count: TokenCounter, max_tokens: int, overlap: int) -> list[Piece]:
    """Split cleaned markdown into pieces of at most ``max_tokens`` tokens."""
    paras = split_paragraphs(text)
    content = [p for p in paras if not PAGE_MARKER.match(p)]
    if not content:
        return []
    pages = [int(m.group(1)) for p in paras if (m := PAGE_MARKER.match(p))]
    whole = "\n\n".join(content)
    whole_tokens = count.count(whole)
    if whole_tokens <= max_tokens:
        first_heading = next((_heading(p)[1] for p in content if p.startswith("#")), None)
        return [Piece(whole, whole_tokens, min(pages, default=None), max(pages, default=None),
                      first_heading)]

    pieces: list[Piece] = []
    units: list[_Unit] = []
    path: list[tuple[int, str]] = []
    page: int | None = None

    def flush() -> None:
        if units:
            pieces.extend(_pack(units, count, max_tokens, overlap))
            units.clear()

    for p in paras:
        m = PAGE_MARKER.match(p)
        if m:
            page = int(m.group(1))
            continue
        if p.startswith("#"):
            level, title = _heading(p)
            path[:] = [(lv, t) for lv, t in path if lv < level] + [(level, title)]
            units.append(_Unit(p, count.count(p), page, _section(path), is_heading=True))
        elif p.lstrip().startswith("|"):
            flush()
            pieces.extend(_split_table(p, _section(path), page, count, max_tokens))
        else:
            for unit_text in _units_of(p, count, max_tokens - _PREFIX_ROOM, overlap):
                units.append(_Unit(unit_text, count.count(unit_text), page, _section(path)))
    flush()
    return pieces


def _units_of(p: str, count: TokenCounter, limit: int, overlap: int) -> list[str]:
    lines = p.splitlines()
    if all(_LIST.match(ln) for ln in lines):
        candidates = lines
    else:
        candidates = [s.strip() for s in _SENTENCE.split(" ".join(lines)) if s.strip()]
    out: list[str] = []
    for c in candidates:
        out.extend([c] if count.count(c) <= limit else _split_words(c, count, limit, overlap))
    return out


def _split_words(text: str, count: TokenCounter, limit: int, overlap: int) -> list[str]:
    """Last resort for one very long sentence: split by words with overlap."""
    words = text.split()
    out: list[str] = []
    start = 0
    while start < len(words):
        end = start + 1
        while end < len(words) and count.count(" ".join(words[start : end + 1])) <= limit:
            end += 1
        out.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        back = end
        while back > start + 1 and count.count(" ".join(words[back - 1 : end])) <= overlap:
            back -= 1
        start = back if back < end else end
    return out


def _pack(units: list[_Unit], count: TokenCounter, max_tokens: int, overlap: int) -> list[Piece]:
    out: list[Piece] = []
    cur: list[_Unit] = []

    def render(items: list[_Unit]) -> str:
        first = items[0]
        prefix = "" if first.is_heading or not first.section else f"[Section: {first.section}]\n"
        return prefix + "\n".join(u.text for u in items)

    def emit(items: list[_Unit]) -> None:
        if not items or all(u.is_heading for u in items):
            return
        text = render(items)
        pages = [u.page for u in items if u.page is not None]
        body = [u for u in items if not u.is_heading] or items
        out.append(Piece(text, count.count(text), min(pages, default=None),
                         max(pages, default=None), body[0].section))

    for u in units:
        if cur and count.count(render(cur + [u])) > max_tokens:
            carry = [cur.pop()] if cur[-1].is_heading else []  # a heading moves with its text
            emit(cur)
            tail: list[_Unit] = []
            if not carry:
                for prev in reversed(cur):
                    if prev.is_heading or prev.section != u.section:
                        break
                    if sum(t.tokens for t in tail) + prev.tokens > overlap:
                        break
                    tail.insert(0, prev)
            cur = carry + tail
        cur.append(u)
        while len(cur) > 1 and count.count(render(cur)) > max_tokens:
            cur.pop(0)
    emit(cur)
    return out


def _split_table(
    table: str, section: str | None, page: int | None, count: TokenCounter, max_tokens: int
) -> list[Piece]:
    prefix = f"[Section: {section}]\n" if section else ""
    whole = prefix + table
    if count.count(whole) <= max_tokens:
        return [Piece(whole, count.count(whole), page, page, section)]
    lines = table.splitlines()
    header = [lines[0]]
    body = lines[1:]
    if body and _TABLE_RULE.match(body[0].strip()):
        header.append(body[0])
        body = body[1:]
    head = prefix + "\n".join(header)
    out: list[Piece] = []
    rows: list[str] = []
    for row in body:
        if rows and count.count(head + "\n" + "\n".join(rows + [row])) > max_tokens:
            text = head + "\n" + "\n".join(rows)
            out.append(Piece(text, count.count(text), page, page, section))
            rows = []
        rows.append(row)
    if rows:
        text = head + "\n" + "\n".join(rows)
        out.append(Piece(text, count.count(text), page, page, section))
    return out
