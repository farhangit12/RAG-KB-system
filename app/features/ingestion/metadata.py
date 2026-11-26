"""Document metadata: validation and flattening to scalars (decision 003).

Fields from the RAG design (title, source, industry, stage, location, access, file
location) use this repo's frontmatter names: ``sector`` for industry, ``founder_stage``
for stage, ``visibility`` for access. ``industry`` and ``stage`` are accepted as aliases.

visibility:
- public:   searchable by every founder.
- internal: Disha-only notes; never indexed (CLAUDE.md content rule).
- private:  one business's own file; needs ``business_id``; only that business sees it.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.core.ports import MetadataValue

VISIBILITIES = {"public", "internal", "private"}
ALIASES = {"industry": "sector", "stage": "founder_stage", "access": "visibility"}
ACCESS_ALIASES = {"shared": "public"}


class MetadataError(ValueError):
    """The document's metadata breaks a rule; the file is skipped and reported."""


def _scalar(value: Any) -> MetadataValue | None:
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    if isinstance(value, list | tuple | set):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ",".join(items) if items else None
    text = str(value).strip()
    return text or None


def normalise(raw: dict[str, Any]) -> dict[str, MetadataValue]:
    """Apply aliases, lower-case the filter fields, flatten lists, validate the rules."""
    meta: dict[str, Any] = {}
    for key, value in raw.items():
        meta[ALIASES.get(key, key)] = value

    visibility = str(meta.get("visibility") or "public").strip().lower()
    visibility = ACCESS_ALIASES.get(visibility, visibility)
    if visibility not in VISIBILITIES:
        raise MetadataError(f"visibility must be one of {sorted(VISIBILITIES)}, got {visibility!r}")
    meta["visibility"] = visibility

    if visibility == "private" and not meta.get("business_id"):
        raise MetadataError("private documents need a business_id")
    if visibility != "private" and meta.get("business_id"):
        raise MetadataError("business_id is only allowed on private documents")
    if not meta.get("type"):
        raise MetadataError("type is missing and could not be inferred from the folder")
    cites_ok = meta.get("publisher") and meta.get("publication_year")
    if meta["type"] == "market_report" and not cites_ok:
        raise MetadataError("market reports need publisher and publication_year")

    for key in ("sector", "founder_stage", "location", "type"):
        if isinstance(meta.get(key), str):
            meta[key] = meta[key].strip().lower()

    valid_until = meta.get("valid_until")
    if valid_until is not None and not isinstance(valid_until, dt.date):
        try:
            meta["valid_until"] = dt.date.fromisoformat(str(valid_until))
        except ValueError as exc:
            raise MetadataError(f"valid_until must be YYYY-MM-DD, got {valid_until!r}") from exc

    out: dict[str, MetadataValue] = {}
    for key, value in meta.items():
        flat = _scalar(value)
        if flat is not None:
            out[key] = flat
    return out

