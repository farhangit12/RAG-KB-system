"""Markdown files with YAML frontmatter (the format described in README.md)."""

from __future__ import annotations

from pathlib import Path

import frontmatter

from app.adapters.loaders.common import infer_type, source_of
from app.core.config import Settings
from app.core.ports import Document


class MarkdownLoader:
    """One Document per markdown file; frontmatter becomes metadata."""

    extensions: tuple[str, ...] = (".md",)

    def load(self, path: Path, root: Path) -> list[Document]:
        """Read ``path``; a missing ``type`` is inferred from the folder."""
        post = frontmatter.load(path)
        meta = dict(post.metadata)
        meta.setdefault("type", infer_type(path, root))
        meta.setdefault("title", path.stem.replace("-", " ").title())
        return [Document(source=source_of(path, root), text=post.content, metadata=meta)]


def build(settings: Settings) -> MarkdownLoader:
    """Factory used by the container."""
    return MarkdownLoader()
