"""Loads markdown files with optional YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter

from app.core.config import Settings
from app.core.ports import Document

FOLDER_TYPES: dict[str, str] = {
    "stories": "story",
    "frameworks": "framework",
    "case-studies": "case_study",
    "faq": "faq",
}
_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def infer_type(source: str) -> str | None:
    """Guess the content type from the first folder of ``source``."""
    return FOLDER_TYPES.get(source.split("/", 1)[0])


class MarkdownLoader:
    """Reads ``.md`` files; frontmatter becomes metadata, the rest is the text."""

    extensions: tuple[str, ...] = (".md", ".markdown")

    def load(self, path: Path, root: Path) -> list[Document]:
        """Load one file. Missing ``type``/``title``/``visibility`` are filled in."""
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        source = path.relative_to(root).as_posix()
        meta = dict(post.metadata)
        if not meta.get("type") and (inferred := infer_type(source)):
            meta["type"] = inferred
        if not meta.get("title"):
            h1 = _H1.search(post.content)
            meta["title"] = h1.group(1).strip() if h1 else path.stem
        meta.setdefault("visibility", "public")
        return [Document(source=source, text=post.content, metadata=meta)]


def build(settings: Settings) -> MarkdownLoader:
    """Factory used by the container."""
    return MarkdownLoader()
