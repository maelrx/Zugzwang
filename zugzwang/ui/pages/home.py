from __future__ import annotations

import os
from typing import Any

import streamlit as st

from zugzwang.infra.env import load_dotenv
from zugzwang.ui.components.metrics import render_kpi_row


WORKING_FEATURES = [
    "Run dry-run, play (1 game), and full run from GUI",
    "Track local jobs with status and logs",
    "Inspect run artifacts (resolved config and reports)",
    "Replay move-by-move with per-ply metrics",
    "Run Stockfish evaluation and save experiment_report_evaluated.json",
]


def render(services: dict[str, Any]) -> None:
    st.title("Home")
    st.caption("Operational overview and quick navigation")

    load_dotenv()
    _render_environment_status()

    artifact_service = services["artifact_service"]
    run_service = services["run_service"]

    runs = artifact_service.list_runs(filters=None)
    run_summaries = [artifact_service.load_run_summary(run.run_dir) for run in runs[:20]]

    completion_values: list[float] = []
    acpl_values: list[float] = []
    total_cost = 0.0
    budget_values: list[float] = []

    for summary in run_summaries:
        report = summary.evaluated_report or summary.report
        if not isinstance(report, dict):
            continue
        completion = report.get("completion_rate")
        acpl = report.get("acpl_overall")
        budget = report.get("budget_utilization")
        cost = report.get("total_cost_usd")
        if isinstance(completion, (int, float)):
            completion_values.append(float(completion))
        if isinstance(acpl, (int, float)):
            acpl_values.append(float(acpl))
        if isinstance(budget, (int, float)):
            budget_values.append(float(budget))
        if isinstance(cost, (int, float)):
            total_cost += float(cost)

    st.subheader("Project Snapshot")
    render_kpi_row(
        [
            ("Runs", len(runs)),
            ("Avg Completion", _avg(completion_values)),
            ("Avg ACPL", _avg(acpl_values)),
            ("Total Cost USD", total_cost),
            ("Avg Budget Util.", _avg(budget_values)),
        ]
    )

    st.subheader("What works now")
    for item in WORKING_FEATURES:
        st.write(f"- {item}")

    st.subheader("How to use")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.write("1. Configure and launch")
        if st.button("Go to Run Lab", use_container_width=True):
            _go_to("Run Lab")
    with col2:
        st.write("2. Monitor live jobs")
        if st.button("Go to Job Monitor", use_container_width=True):
            _go_to("Job Monitor")
    with col3:
        st.write("3. Inspect run artifacts")
        if st.button("Go to Run Explorer", use_container_width=True):
            _go_to("Run Explorer")
    with col4:
        st.write("4. Replay and evaluate")
        row_left, row_right = st.columns(2)
        with row_left:
            if st.button("Replay", use_container_width=True):
                _go_to("Game Replay")
        with row_right:
            if st.button("Evaluate", use_container_width=True):
                _go_to("Evaluation")

    st.subheader("Recent Runs")
    if not runs:
        st.info("No runs found in results/runs")
    else:
        st.dataframe(
            [
                {
                    "run_id": run.run_id,
                    "created_at_utc": run.created_at_utc,
                    "config_hash": run.config_hash,
                    "report": run.report_exists,
                    "evaluated_report": run.evaluated_report_exists,
                }
                for run in runs[:15]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Job Snapshot")
    jobs = run_service.list_jobs(refresh=True)
    running_count = sum(1 for job in jobs if job.get("status") == "running")
    completed_count = sum(1 for job in jobs if job.get("status") == "completed")
    failed_count = sum(1 for job in jobs if job.get("status") == "failed")

    render_kpi_row(
        [
            ("Running Jobs", running_count),
            ("Completed Jobs", completed_count),
            ("Failed Jobs", failed_count),
            ("Tracked Jobs", len(jobs)),
        ]
    )


def _render_environment_status() -> None:
    st.subheader("Environment")
    env_rows = [
        (".env file", "yes" if os.path.exists(".env") else "no"),
        ("ZAI_API_KEY", _mask_presence(os.environ.get("ZAI_API_KEY"))),
        ("STOCKFISH_PATH", _stockfish_status()),
    ]

    st.dataframe(
        [{"item": label, "status": status} for label, status in env_rows],
        hide_index=True,
        use_container_width=True,
    )


def _mask_presence(value: str | None) -> str:
    if value and value.strip():
        return "set"
    return "missing"


def _stockfish_status() -> str:
    value = os.environ.get("STOCKFISH_PATH")
    if not value:
        return "not set (PATH fallback)"
    return "found" if os.path.exists(value) else "set but missing"


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _go_to(page: str) -> None:
    st.session_state["nav_page"] = page
    st.rerun()
