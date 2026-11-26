"""PDF, DOCX, TXT and CSV loaders. Every file is turned into markdown.

Metadata for these files comes from a sidecar YAML file next to them, named
``<file name>.meta.yaml`` (e.g. ``report.pdf.meta.yaml``), using the same fields as
markdown frontmatter.

PDF and DOCX use Docling (MIT): it keeps headings, lists and tables and runs OCR on
scanned pages. PyMuPDF is not used because of its AGPL licence (decision 010). If Docling
is not installed, pypdf (PDF) and python-docx (DOCX) are used, without tables or OCR.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import yaml

from app.adapters.loaders.common import infer_type, page_marker, source_of
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.ports import Document

log = get_logger(__name__)


def decode_bytes(data: bytes) -> str:
    """UTF-16 when it has a BOM, else UTF-8 (with or without BOM), else Windows-1252."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def sidecar_metadata(path: Path) -> dict[str, Any]:
    """Read ``<file>.meta.yaml`` if it exists."""
    side = path.with_name(path.name + ".meta.yaml")
    if not side.exists():
        return {}
    data = yaml.safe_load(side.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{side.name} must contain a YAML mapping")
    return data


def csv_to_markdown(data: bytes, rows_per_block: int) -> str:
    """CSV as markdown tables of ``rows_per_block`` rows, each repeating the header."""
    rows = [r for r in csv.reader(io.StringIO(decode_bytes(data))) if any(c.strip() for c in r)]
    if not rows:
        return ""
    header = [c.strip() for c in rows[0]]
    head = "| " + " | ".join(header) + " |\n|" + "---|" * len(header)
    blocks = []
    body = rows[1:]
    for start in range(0, max(len(body), 1), rows_per_block):
        group = body[start : start + rows_per_block]
        lines = ["| " + " | ".join(c.strip().replace("|", "/") for c in r) + " |" for r in group]
        blocks.append("\n".join([head, *lines]))
    return "\n\n".join(blocks)


def docling_to_markdown(path: Path) -> str:
    """Convert with Docling, adding a page marker whenever the page changes."""
    from docling.document_converter import DocumentConverter

    doc = DocumentConverter().convert(str(path)).document
    out: list[str] = []
    page = None
    for item, _level in doc.iterate_items():
        prov = getattr(item, "prov", None) or []
        item_page = getattr(prov[0], "page_no", None) if prov else None
        if item_page is not None and item_page != page:
            page = item_page
            out.append(page_marker(page))
        label = str(getattr(item, "label", "")).lower()
        if "page_header" in label or "page_footer" in label:
            continue
        if "table" in label:
            try:
                out.append(item.export_to_markdown(doc=doc))
            except TypeError:
                out.append(item.export_to_markdown())
            continue
        text = (getattr(item, "text", "") or "").strip()
        if not text:
            continue
        if "section_header" in label or label.endswith("title"):
            level = int(getattr(item, "level", 1) or 1)
            out.append(f"{'#' * min(level + 1, 6)} {text}")
        elif "list_item" in label:
            out.append(f"- {text}")
        else:
            out.append(text)
    return "\n\n".join(out)


def pdf_basic_to_markdown(path: Path) -> str:
    """pypdf fallback: plain text per page with page markers."""
    from pypdf import PdfReader

    parts = []
    for n, page in enumerate(PdfReader(str(path)).pages, start=1):
        parts.append(page_marker(n))
        parts.append(page.extract_text() or "")
    return "\n\n".join(parts)


def docx_basic_to_markdown(path: Path) -> str:
    """python-docx fallback: headings, list items, paragraphs, then tables."""
    from docx import Document as DocxDocument

    d = DocxDocument(str(path))
    out = []
    for p in d.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = (p.style.name if p.style is not None else "").lower()
        if style.startswith("heading") and style.split()[-1].isdigit():
            out.append(f"{'#' * min(int(style.split()[-1]) + 1, 6)} {text}")
        elif style == "title":
            out.append(f"# {text}")
        elif "list" in style:
            out.append(f"- {text}")
        else:
            out.append(text)
    for t in d.tables:
        rows = [[c.text.strip().replace("|", "/") for c in r.cells] for r in t.rows]
        if rows:
            lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
            lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
            out.append("\n".join(lines))
    return "\n\n".join(out)


class FileLoader:
    """Loads PDF, DOCX, TXT and CSV into markdown Documents."""

    extensions: tuple[str, ...] = (".pdf", ".docx", ".txt", ".csv")

    def __init__(self, csv_rows_per_block: int = 25) -> None:
        self._csv_rows = csv_rows_per_block

    def load(self, path: Path, root: Path) -> list[Document]:
        """Read ``path`` with its sidecar metadata."""
        ext = path.suffix.lower()
        if ext == ".txt":
            text = decode_bytes(path.read_bytes())
        elif ext == ".csv":
            text = csv_to_markdown(path.read_bytes(), self._csv_rows)
        elif ext in (".pdf", ".docx"):
            try:
                text = docling_to_markdown(path)
            except ImportError:
                log.warning("docling not installed, using basic extractor",
                            extra={"file": path.name})
                basic = pdf_basic_to_markdown if ext == ".pdf" else docx_basic_to_markdown
                text = basic(path)
        else:
            raise ValueError(f"FileLoader cannot read {ext}")
        meta = sidecar_metadata(path)
        meta.setdefault("type", infer_type(path, root))
        meta.setdefault("title", path.stem.replace("-", " ").replace("_", " ").title())
        meta.setdefault("file_type", ext.lstrip("."))
        return [Document(source=source_of(path, root), text=text, metadata=meta)]


def build(settings: Settings) -> FileLoader:
    """Factory used by the container."""
    return FileLoader(settings.csv_rows_per_block)
