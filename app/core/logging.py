"""Structured logging with the standard library.

Usage::

    log = get_logger(__name__)
    log.info("ingested", extra={"files": 4, "chunks": 12})

Extra fields are printed as ``key=value`` (human mode) or as JSON keys (``LOG_JSON=true``).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}


class JsonFormatter(logging.Formatter):
    """One JSON object per line; good for log collectors in production."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **_extras(record),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class KeyValueFormatter(logging.Formatter):
    """Readable single-line logs for local development."""

    def format(self, record: logging.LogRecord) -> str:
        fields = " ".join(f"{k}={v}" for k, v in _extras(record).items())
        line = f"{record.levelname:<7} {record.name}: {record.getMessage()}"
        if fields:
            line = f"{line} | {fields}"
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Set up the root logger once; safe to call repeatedly."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if json_logs else KeyValueFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
