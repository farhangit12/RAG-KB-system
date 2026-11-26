"""Checks the knowledge base files follow the content format."""

from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from tests.conftest import REPO_ROOT

CONTENT = REPO_ROOT / "content"
FILES = sorted(CONTENT.rglob("*.md"))
REQUIRED = {"title", "type", "people", "founder_stage", "sector", "topics", "date", "visibility"}
TYPES = {"story", "framework", "case_study", "faq"}
STAGES = {"idea", "early", "traction"}


def test_content_folders_exist() -> None:
    for folder in ("stories", "frameworks", "case-studies", "faq"):
        assert (CONTENT / folder).is_dir()


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(CONTENT).as_posix())
def test_frontmatter_is_valid(path: Path) -> None:
    meta = frontmatter.load(path).metadata
    assert meta.keys() >= REQUIRED, f"missing: {REQUIRED - meta.keys()}"
    assert meta["type"] in TYPES
    assert meta["founder_stage"] in STAGES
    assert meta["visibility"] in {"public", "internal"}
    assert isinstance(meta["people"], list)
    assert isinstance(meta["topics"], list)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(CONTENT).as_posix())
def test_samples_are_marked(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "SAMPLE" in text:
        assert "SAMPLE, replace with real content" in text
