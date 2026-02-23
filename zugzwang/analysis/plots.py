from __future__ import annotations

from typing import Sequence


def format_ci_line(label: str, mean: float, ci_low: float, ci_high: float, *, precision: int = 4) -> str:
    return f"{label}: mean={mean:.{precision}f}, ci=[{ci_low:.{precision}f}, {ci_high:.{precision}f}]"


def ascii_histogram(
    values: Sequence[float],
    *,
    bins: int = 8,
    width: int = 24,
    label: str = "values",
    precision: int = 3,
) -> str:
    data = [float(item) for item in values]
    if not data:
        return f"{label}: (no data)"
    if bins <= 0:
        bins = 1
    if width <= 0:
        width = 1

    low = min(data)
    high = max(data)
    if low == high:
        return f"{label}: {low:.{precision}f} (constant x{len(data)})"

    span = high - low
    counts = [0 for _ in range(bins)]
    for value in data:
        position = (value - low) / span
        index = int(position * bins)
        if index >= bins:
            index = bins - 1
        counts[index] += 1

    max_count = max(counts) if counts else 1
    lines = [f"{label} distribution:"]
    for idx, count in enumerate(counts):
        start = low + span * idx / bins
        end = low + span * (idx + 1) / bins
        bar_len = int(round((count / max_count) * width)) if max_count > 0 else 0
        bar = "#" * max(0, bar_len)
        lines.append(
            f"  [{start:.{precision}f}, {end:.{precision}f}) {bar} ({count})"
        )
    return "\n".join(lines)
