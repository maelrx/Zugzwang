from __future__ import annotations

from typing import Any

import streamlit as st


def render(services: dict[str, Any]) -> None:
    st.title("Guided Flow")
    st.caption("Use this page if you want a direct, step-by-step operation path")

    _render_prerequisites()
    _render_steps()

    run_service = services["run_service"]
    jobs = run_service.list_jobs(refresh=True)
    if jobs:
        st.subheader("Latest activity")
        st.dataframe(
            [
                {
                    "job_id": job.get("job_id"),
                    "type": job.get("job_type"),
                    "status": job.get("status"),
                    "run_id": job.get("run_id"),
                }
                for job in jobs[:8]
            ],
            hide_index=True,
            use_container_width=True,
        )


def _render_prerequisites() -> None:
    st.subheader("Prerequisites")
    checks = [
        ("1. Configure .env", "Set ZAI_API_KEY in .env"),
        ("2. Optional evaluation", "Set STOCKFISH_PATH for deterministic evaluation"),
        ("3. Start with a small run", "Use Play or Dry Run before full Run"),
    ]
    for title, description in checks:
        st.write(f"{title}: {description}")


def _render_steps() -> None:
    st.subheader("Workflow")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**Step 1**")
        st.write("Configure baseline and overrides")
        if st.button("Open Run Lab", use_container_width=True):
            _go_to("Run Lab")

    with col2:
        st.markdown("**Step 2**")
        st.write("Launch and monitor job state/logs")
        if st.button("Open Job Monitor", use_container_width=True):
            _go_to("Job Monitor")

    with col3:
        st.markdown("**Step 3**")
        st.write("Inspect artifacts and run summary")
        if st.button("Open Run Explorer", use_container_width=True):
            _go_to("Run Explorer")

    with col4:
        st.markdown("**Step 4**")
        st.write("Replay and evaluate quality metrics")
        row_left, row_right = st.columns(2)
        with row_left:
            if st.button("Replay", use_container_width=True):
                _go_to("Game Replay")
        with row_right:
            if st.button("Evaluate", use_container_width=True):
                _go_to("Evaluation")


def _go_to(page: str) -> None:
    st.session_state["nav_page"] = page
    st.rerun()
