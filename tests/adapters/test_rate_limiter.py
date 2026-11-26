from __future__ import annotations

from app.adapters.ratelimiters.memory import MemoryRateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_per_key() -> None:
    clock = Clock()
    rl = MemoryRateLimiter(limit=2, window_seconds=60, clock=clock)
    assert rl.allow("a") and rl.allow("a")
    assert not rl.allow("a")
    assert rl.allow("b")  # other keys are independent
    clock.now = 61
    assert rl.allow("a")  # window passed
