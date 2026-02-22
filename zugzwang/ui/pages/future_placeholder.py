from __future__ import annotations

import streamlit as st


def render(title: str, description: str) -> None:
    st.title(title)
    st.info(description)
