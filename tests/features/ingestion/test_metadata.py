from __future__ import annotations

from datetime import date

from app.features.ingestion.metadata import flatten_metadata


def test_flattens_lists_dates_and_drops_none() -> None:
    meta = {
        "title": "BHUMI",
        "people": ["Sara", "Anshuman"],
        "topics": ["positioning", "Social Impact"],
        "date": date(2026, 5, 1),
        "draft": None,
        "weight": 2,
        "pinned": True,
    }
    flat = flatten_metadata(meta)
    assert flat["people"] == "Sara, Anshuman"
    assert flat["people_sara"] is True
    assert flat["people_anshuman"] is True
    assert flat["topics_social_impact"] is True
    assert flat["date"] == "2026-05-01"
    assert "draft" not in flat
    assert flat["weight"] == 2
    assert flat["pinned"] is True
    assert all(isinstance(v, str | int | float | bool) for v in flat.values())
