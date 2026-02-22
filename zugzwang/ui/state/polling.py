from __future__ import annotations

import time


def should_poll(last_poll_ts: float | None, interval_seconds: float = 2.0) -> bool:
    if last_poll_ts is None:
        return True
    return (time.monotonic() - last_poll_ts) >= interval_seconds


def now_monotonic() -> float:
    return time.monotonic()
