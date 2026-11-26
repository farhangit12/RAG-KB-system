from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter, KeyValueFormatter


def _record() -> logging.LogRecord:
    record = logging.LogRecord("disha.test", logging.INFO, __file__, 1, "ingested", None, None)
    record.files = 4
    return record


def test_json_formatter_includes_extra_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["msg"] == "ingested"
    assert payload["level"] == "INFO"
    assert payload["files"] == 4


def test_key_value_formatter_is_readable() -> None:
    line = KeyValueFormatter().format(_record())
    assert "ingested" in line
    assert "files=4" in line
