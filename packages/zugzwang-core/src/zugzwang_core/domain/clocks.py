"""Clock handling.

All scientific timestamps are UTC. Operational monotonic time is kept separate
so wall-clock adjustments never corrupt latency accounting.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Current UTC time, timezone-aware."""
    return datetime.now(UTC)


def monotonic_seconds() -> float:
    """Monotonic clock in seconds (operational only, never scientific)."""
    return time.monotonic()


def to_iso_z(value: datetime) -> str:
    """Serialize a datetime to a canonical UTC string with a ``Z`` suffix."""
    if value.tzinfo is None:
        raise ValueError("naive datetime cannot be serialized to ISO-8601 Z")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def from_iso_z(value: str) -> datetime:
    """Parse an ISO-8601 string into a UTC-aware datetime."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no timezone")
    return parsed.astimezone(UTC)
