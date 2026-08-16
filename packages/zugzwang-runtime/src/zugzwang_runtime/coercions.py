"""Safe coercions from manifest JsonValue configs to typed scalars."""

from __future__ import annotations

from zugzwang_core.domain.events import JsonValue


def as_int(value: JsonValue | None, default: int) -> int:
    """Coerce a config value to int, rejecting non-numeric types."""
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"config value must be numeric, got boolean {value!r}")
    if isinstance(value, (int, float, str)):
        return int(value)
    raise ValueError(f"config value must be numeric, got {value!r}")


def as_float(value: JsonValue | None, default: float) -> float:
    """Coerce a config value to float, rejecting non-numeric types."""
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"config value must be numeric, got boolean {value!r}")
    if isinstance(value, (int, float, str)):
        return float(value)
    raise ValueError(f"config value must be numeric, got {value!r}")
