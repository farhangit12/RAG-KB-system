"""Picks a loader by file extension: markdown, or PDF / DOCX / TXT / CSV."""

from __future__ import annotations

from pathlib import Path

from app.adapters.loaders.files import FileLoader
from app.adapters.loaders.markdown import MarkdownLoader
from app.core.config import Settings
from app.core.ports import Document, DocumentLoader


class AutoLoader:
    """Delegates to the loader that handles the file's extension."""

    def __init__(self, loaders: list[DocumentLoader]) -> None:
        self._by_ext = {ext: ld for ld in loaders for ext in ld.extensions}
        self.extensions: tuple[str, ...] = tuple(sorted(self._by_ext))

    def load(self, path: Path, root: Path) -> list[Document]:
        """Load ``path`` with the matching loader."""
        loader = self._by_ext.get(path.suffix.lower())
        if loader is None:
            supported = ", ".join(self.extensions)
            raise ValueError(f"No loader for {path.suffix}. Supported: {supported}")
        return loader.load(path, root)


def build(settings: Settings) -> AutoLoader:
    """Factory used by the container."""
    return AutoLoader([MarkdownLoader(), FileLoader(settings.csv_rows_per_block)])
