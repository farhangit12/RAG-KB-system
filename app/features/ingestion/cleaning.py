"""Text cleaning, following the remove / preserve lists in the RAG design.

Remove: blank lines, extra spaces, broken line breaks, repeated headers and footers,
        page numbers, duplicate paragraphs, encoding errors and control characters.
Keep:   headings, paragraphs, lists, tables, figures' captions, dates and currency values.

Input and output are markdown with optional ``<!-- page: N -->`` marker lines.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

PAGE_MARKER = re.compile(r"^<!-- page: (\d+) -->$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​‌‍﻿�]")
_SPACES = re.compile(r"[ \t ]+")
_PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.IGNORECASE)
_LIST = re.compile(r"^(\s*)([-*•]\s+|\d+[.)]\s+)")
_SENTENCE_END = (".", "!", "?", ":", ";", "।", '"', "”", ")")


def fix_encoding(text: str) -> str:
    """Normalise Unicode and drop control and replacement characters."""
    return _CONTROL.sub("", unicodedata.normalize("NFC", text))


def _is_structural(line: str) -> bool:
    s = line.lstrip()
    return s.startswith(("#", "|")) or bool(_LIST.match(line)) or bool(PAGE_MARKER.match(s))


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; page markers and headings are their own paragraphs."""
    paras: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if cur:
                paras.append("\n".join(cur))
                cur = []
        elif PAGE_MARKER.match(stripped) or stripped.startswith("#"):
            if cur:
                paras.append("\n".join(cur))
                cur = []
            paras.append(stripped)
        else:
            cur.append(line.rstrip())
    if cur:
        paras.append("\n".join(cur))
    return paras


def _repeated_lines(paras: list[str], min_pages: int) -> set[str]:
    """Short lines that appear on ``min_pages`` or more different pages (headers, footers)."""
    seen: dict[str, set[int]] = {}
    page = 0
    for p in paras:
        m = PAGE_MARKER.match(p)
        if m:
            page = int(m.group(1))
            continue
        if p.startswith(("|", "#")):
            continue
        for line in p.splitlines():
            key = _SPACES.sub(" ", line).strip().lower()
            if 0 < len(key) <= 120:
                seen.setdefault(key, set()).add(page)
    return {k for k, pages in seen.items() if len(pages) >= min_pages}


def join_broken_lines(lines: list[str]) -> list[str]:
    """Join lines split mid-sentence by a PDF layout; list items stay separate."""
    out: list[str] = []
    for line in lines:
        continues = out and not out[-1].endswith(_SENTENCE_END)
        if continues and not _LIST.match(line) and not _LIST.match(out[-1]):
            if out[-1].endswith("-") and line[:1].islower():
                out[-1] = out[-1][:-1] + line  # re-join a hyphenated word
            else:
                out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _clean_paragraph(p: str, repeated: set[str]) -> str:
    lines = []
    for line in p.splitlines():
        squashed = _SPACES.sub(" ", line).strip()
        if not squashed or squashed.lower() in repeated or _PAGE_NUMBER.match(squashed):
            continue
        lines.append(squashed if not line.lstrip().startswith("|") else line.strip())
    if not lines:
        return ""
    if lines[0].startswith(("|", "#")):
        return "\n".join(lines)  # tables and headings keep their exact lines
    return "\n".join(join_broken_lines(lines))


def clean_markdown(text: str, min_repeat_pages: int = 3) -> str:
    """Return cleaned markdown; page markers are kept for citations."""
    paras = split_paragraphs(fix_encoding(text))
    repeated = _repeated_lines(paras, min_repeat_pages)
    out: list[str] = []
    seen: set[str] = set()
    for p in paras:
        if PAGE_MARKER.match(p):
            out.append(p)
            continue
        cleaned = _clean_paragraph(p, repeated)
        if not cleaned:
            continue
        if not cleaned.startswith("#"):  # headings may repeat; paragraphs and tables may not
            key = hashlib.sha256(re.sub(r"\s+", " ", cleaned.lower()).encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key)
        out.append(cleaned)
    return "\n\n".join(out)
