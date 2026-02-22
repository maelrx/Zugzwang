from __future__ import annotations

from typing import Any

import streamlit as st


def render_kpi_row(values: list[tuple[str, Any]]) -> None:
    if not values:
        return
    cols = st.columns(len(values))
    for col, (label, value) in zip(cols, values, strict=False):
        col.metric(label, _format_value(value))


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}" if abs(value) < 10 else f"{value:.2f}"
    return str(value)
