"""Sliding-window rate limiter kept in process memory.

Fine for one instance. With several instances each keeps its own counts, so move to a
shared store (e.g. Redis) behind the same RateLimiter port when scaling out.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from app.core.config import Settings

_MAX_KEYS = 10_000


class MemoryRateLimiter:
    """Allows ``limit`` requests per ``window_seconds`` per key."""

    def __init__(
        self, limit: int, window_seconds: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a request; False if ``key`` already used its quota in this window."""
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._prune(cutoff)
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def _prune(self, cutoff: float) -> None:
        self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}


def build(settings: Settings) -> MemoryRateLimiter:
    """Factory used by the container."""
    return MemoryRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
