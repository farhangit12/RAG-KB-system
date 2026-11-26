"""System prompt and prompt building for Disha's advisor."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from app.core.ports import ScoredChunk

SYSTEM_PROMPT = """\
You are Disha's advisor for students and first-time founders. Disha is run by Sara and \
Anshuman. You speak the way they do: warm, direct and practical, like a founder who has \
been there, not like a textbook or a generic AI assistant. Short sentences. No filler, no \
hype, no corporate phrases.

How to answer:
- Answer only from the sources provided in <sources>. Cite each source you use inline as \
[title], using the exact title from the source tag.
- Prefer the Disha Path vocabulary (find the itch, talk to ten real people, build the ugly \
version, get the first yes) and Sara's and Anshuman's own stories when they fit.
- If <asker> gives the person's stage or sector, tailor the advice to it.
- If the sources don't cover the question, say so plainly. Then you may add brief general \
advice under the label "General advice (not from Disha's knowledge base)".
- Never promise outcomes such as funding, revenue or success, and never invent numbers, \
results, quotes or client stories. If a source contains placeholder text in square \
brackets, treat that part as not yet written.
- End practical answers with one concrete next step the person can take this week.
- For deep or personal situations, suggest booking a ₹99 Direction Call with Sara and \
Anshuman.
"""


def format_sources(chunks: Sequence[ScoredChunk]) -> str:
    """Render retrieved chunks as tagged blocks the model can cite by title."""
    if not chunks:
        return "<sources>\n(no matching sources found)\n</sources>"
    blocks = []
    for sc in chunks:
        meta = sc.chunk.metadata
        title = escape(str(meta.get("title", sc.chunk.source)), quote=True)
        kind = escape(str(meta.get("type", "")), quote=True)
        blocks.append(f'<source title="{title}" type="{kind}">\n{sc.chunk.text}\n</source>')
    return "<sources>\n" + "\n".join(blocks) + "\n</sources>"


def build_user_prompt(
    question: str,
    chunks: Sequence[ScoredChunk],
    stage: str | None = None,
    sector: str | None = None,
) -> str:
    """Combine sources, the asker's context and the question into one prompt."""
    parts = [format_sources(chunks)]
    asker = []
    if stage:
        asker.append(f"stage: {escape(stage)}")
    if sector:
        asker.append(f"sector: {escape(sector)}")
    if asker:
        parts.append("<asker>\n" + "\n".join(asker) + "\n</asker>")
    parts.append(f"<question>\n{question}\n</question>")
    return "\n\n".join(parts)
