"""Turn frontmatter into flat, filterable chunk metadata.

Vector stores can only filter on scalar values, so:
- scalars are kept as they are;
- dates become ISO strings;
- lists become a readable string (``people: "Sara, Anshuman"``) plus one boolean flag
  per item (``people_sara: True``) so you can filter "chunks about Sara".
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from app.core.metadata_keys import flag_key
from app.core.ports import MetadataValue


def flatten_metadata(meta: Mapping[str, Any]) -> dict[str, MetadataValue]:
    """Return a copy of ``meta`` that every vector store can store and filter on."""
    out: dict[str, MetadataValue] = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float | str):
            out[key] = value
        elif isinstance(value, date | datetime):
            out[key] = value.isoformat()
        elif isinstance(value, list | tuple | set):
            items = [str(v) for v in value if v is not None]
            out[key] = ", ".join(items)
            for item in items:
                out[flag_key(key, item)] = True
        else:
            out[key] = str(value)
    return out
