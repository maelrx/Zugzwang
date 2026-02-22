from __future__ import annotations

import time
from typing import Any

import streamlit as st

from zugzwang.ui.components.metrics import render_kpi_row


def render(services: dict[str, Any]) -> None:
    st.title("Job Monitor")
    st.caption("Track local jobs, progress, logs, and jump to related pages")

    run_service = services["run_service"]
    evaluation_service = services["evaluation_service"]

    jobs = run_service.list_jobs(refresh=True)
    running_jobs = [job for job in jobs if job.get("status") == "running"]

    render_kpi_row(
        [
            ("Tracked Jobs", len(jobs)),
            ("Running", len(running_jobs)),
            ("Completed", sum(1 for job in jobs if job.get("status") == "completed")),
            ("Failed", sum(1 for job in jobs if job.get("status") == "failed")),
        ]
    )

    if not jobs:
        st.info("No jobs found yet. Launch one from Run Lab or Evaluation.")
        return

    statuses = sorted({str(job.get("status", "unknown")) for job in jobs})
    types = sorted({str(job.get("job_type", "unknown")) for job in jobs})

    col_filters_left, col_filters_right = st.columns(2)
    with col_filters_left:
        selected_statuses = st.multiselect("Status filter", statuses, default=statuses)
    with col_filters_right:
        selected_types = st.multiselect("Type filter", types, default=types)

    filtered_jobs = [
        job
        for job in jobs
        if str(job.get("status", "unknown")) in selected_statuses
        and str(job.get("job_type", "unknown")) in selected_types
    ]

    st.dataframe(
        [
            {
                "job_id": job.get("job_id"),
                "job_type": job.get("job_type"),
                "status": job.get("status"),
                "created_at_utc": job.get("created_at_utc"),
                "run_id": job.get("run_id"),
                "run_dir": job.get("run_dir"),
            }
            for job in filtered_jobs
        ],
        use_container_width=True,
        hide_index=True,
    )

    if not filtered_jobs:
        st.warning("No jobs after filters")
        return

    default_job_id = _pick_default_job_id(filtered_jobs)
    job_ids = [str(job.get("job_id")) for job in filtered_jobs if job.get("job_id")]

    if "job_monitor_selected_job" not in st.session_state or st.session_state["job_monitor_selected_job"] not in job_ids:
        st.session_state["job_monitor_selected_job"] = default_job_id

    selected_job_id = st.selectbox("Job", job_ids, key="job_monitor_selected_job")
    selected_job = next((job for job in filtered_jobs if job.get("job_id") == selected_job_id), None)

    if selected_job is None:
        st.warning("Select a valid job")
        return

    status = str(selected_job.get("status", "queued"))
    st.subheader(f"Selected Job: {selected_job_id}")
    st.write(f"Type: {selected_job.get('job_type')} | Status: {status}")

    run_id = selected_job.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        st.session_state["selected_run_id"] = run_id

    col_left, col_right, col_third = st.columns(3)
    with col_left:
        if status == "running":
            if st.button("Cancel Job", use_container_width=True):
                result = run_service.cancel_run(selected_job_id)
                if result.ok:
                    st.success(result.message)
                else:
                    st.error(result.message)
    with col_right:
        auto_refresh = st.checkbox("Auto-refresh every 2s", value=True)
    with col_third:
        log_chars = st.selectbox("Log tail size", [2000, 4000, 8000, 12000], index=2)

    job_type = str(selected_job.get("job_type", "run"))
    if job_type in {"run", "play"}:
        progress = run_service.get_run_progress(selected_job_id)
        _render_run_progress(progress, max_chars=log_chars)
    else:
        eval_result = evaluation_service.get_evaluation_result(selected_job_id)
        _render_eval_result(eval_result, max_chars=log_chars)

    if auto_refresh and running_jobs:
        time.sleep(2)
        st.rerun()


def _render_run_progress(progress, max_chars: int) -> None:
    st.subheader("Run Progress")
    target = progress.games_target or 0
    if target > 0:
        completion = min(1.0, progress.games_written / target)
        st.progress(completion, text=f"{progress.games_written}/{target} games")
    else:
        st.write(f"Games written: {progress.games_written}")

    render_kpi_row(
        [
            ("Status", progress.status),
            ("Run ID", progress.run_id),
            ("Run Dir", progress.run_dir),
            ("Budget Stop", progress.stopped_due_to_budget),
            ("Reason", progress.budget_stop_reason),
        ]
    )

    row_left, row_right = st.columns(2)
    with row_left:
        if st.button("Open Run Explorer", use_container_width=True):
            st.session_state["nav_page"] = "Run Explorer"
            st.rerun()
    with row_right:
        if st.button("Open Game Replay", use_container_width=True):
            st.session_state["nav_page"] = "Game Replay"
            st.rerun()

    if progress.latest_report:
        with st.expander("Latest report snapshot", expanded=False):
            st.json(progress.latest_report)

    st.subheader("Logs")
    tail = progress.log_tail or "(no logs yet)"
    st.code(tail[-max_chars:])


def _render_eval_result(result, max_chars: int) -> None:
    st.subheader("Evaluation Result")
    render_kpi_row(
        [
            ("Status", result.status),
            ("Output report", result.output_report),
        ]
    )
    if result.payload:
        with st.expander("Evaluation payload", expanded=False):
            st.json(result.payload)

    row_left, row_right = st.columns(2)
    with row_left:
        if st.button("Open Run Explorer", use_container_width=True):
            st.session_state["nav_page"] = "Run Explorer"
            st.rerun()
    with row_right:
        if st.button("Open Evaluation page", use_container_width=True):
            st.session_state["nav_page"] = "Evaluation"
            st.rerun()

    st.subheader("Logs")
    tail = result.log_tail or "(no logs yet)"
    st.code(tail[-max_chars:])


def _pick_default_job_id(jobs: list[dict[str, Any]]) -> str:
    running = [job for job in jobs if job.get("status") == "running"]
    source = running if running else jobs
    first = source[0].get("job_id")
    return str(first)
