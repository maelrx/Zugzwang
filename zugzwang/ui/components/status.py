from __future__ import annotations

import streamlit as st


STATUS_ICON = {
    "queued": "[queued]",
    "running": "[running]",
    "completed": "[ok]",
    "failed": "[failed]",
    "canceled": "[canceled]",
}


def render_status_badge(status: str) -> None:
    icon = STATUS_ICON.get(status, "[unknown]")
    st.write(f"{icon} **{status}**")
