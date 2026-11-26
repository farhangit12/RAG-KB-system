from __future__ import annotations

import datetime as dt

import pytest

from app.features.ingestion.metadata import MetadataError, normalise


def test_aliases_lists_and_dates_are_flattened() -> None:
    out = normalise({"type": "Case_Study", "industry": "FoodTech", "stage": "MVP",
                     "people": ["Sara", "Anshuman"], "access": "shared",
                     "valid_until": dt.date(2027, 3, 31)})
    assert out == {"type": "case_study", "sector": "foodtech", "founder_stage": "mvp",
                   "people": "Sara,Anshuman", "visibility": "public", "valid_until": "2027-03-31"}


@pytest.mark.parametrize(
    ("meta", "message"),
    [
        ({"type": "upload", "visibility": "private"}, "business_id"),
        ({"type": "faq", "business_id": "b1"}, "only allowed on private"),
        ({"type": "market_report"}, "publisher"),
        ({"visibility": "public"}, "type is missing"),
        ({"type": "faq", "visibility": "secret"}, "visibility"),
        ({"type": "scheme", "valid_until": "31/03/2027"}, "YYYY-MM-DD"),
    ],
)
def test_rules(meta: dict, message: str) -> None:
    with pytest.raises(MetadataError, match=message):
        normalise(meta)
