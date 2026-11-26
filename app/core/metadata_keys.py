"""Naming rule for list-item flags in chunk metadata, shared by ingestion and retrieval.

A frontmatter list like ``topics: [pitch, Social Impact]`` is stored as flags
``topics_pitch: True`` and ``topics_social_impact: True``.
"""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug(value: object) -> str:
    """Lower-case, underscores only: ``"Social Impact"`` -> ``"social_impact"``."""
    return _NON_ALNUM.sub("_", str(value).lower()).strip("_")


def flag_key(field: str, value: object) -> str:
    """Metadata key of the boolean flag for one list item, e.g. ``topics_pitch``."""
    return f"{field}_{slug(value)}"
