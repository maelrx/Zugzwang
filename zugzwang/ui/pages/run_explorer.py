from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from zugzwang.ui.components.metrics import render_kpi_row


def render(services: dict[str, Any]) -> None:
    st.title("Run Explorer")
    st.caption("Browse run artifacts, compare runs, and jump to replay/evaluation")

    artifact_service = services["artifact_service"]

    query = st.text_input("Filter runs", value="")
    evaluated_only = st.checkbox("Only runs with evaluated report", value=False)

    runs = artifact_service.list_runs(filters={"query": query, "evaluated_only": evaluated_only})
    if not runs:
        st.info("No runs matched the filter")
        return

    run_id_to_path = {run.run_id: run.run_dir for run in runs}
    run_ids = list(run_id_to_path.keys())

    selected_run_default = st.session_state.get("selected_run_id")
    default_index = run_ids.index(selected_run_default) if selected_run_default in run_ids else 0
    selected_run = st.selectbox("Run", run_ids, index=default_index)
    st.session_state["selected_run_id"] = selected_run

    summary = artifact_service.load_run_summary(run_id_to_path[selected_run])

    st.subheader("Run Summary")
    report = summary.evaluated_report or summary.report or {}
    render_kpi_row(
        [
            ("Run ID", summary.run_meta.run_id),
            ("Games", summary.game_count),
            ("Completion", report.get("completion_rate")),
            ("ACPL", report.get("acpl_overall")),
            ("Total Cost USD", report.get("total_cost_usd")),
            ("Budget Util.", report.get("budget_utilization")),
        ]
    )

    action_left, action_right = st.columns(2)
    with action_left:
        if st.button("Open Game Replay", use_container_width=True):
            st.session_state["nav_page"] = "Game Replay"
            st.rerun()
    with action_right:
        if st.button("Open Evaluation", use_container_width=True):
            st.session_state["nav_page"] = "Evaluation"
            st.rerun()

    st.subheader("Artifacts")
    artifacts = [
        "resolved_config.yaml",
        "experiment_report.json",
        "experiment_report_evaluated.json",
    ]
    available = [item for item in artifacts if Path(summary.run_meta.run_dir, item).exists()]
    selected_artifact = st.selectbox("Artifact", available)

    artifact_text = artifact_service.load_artifact_text(summary.run_meta.run_dir, selected_artifact)

    view_mode = st.radio("View mode", ["Parsed", "Raw"], horizontal=True)
    if view_mode == "Raw":
        st.code(artifact_text)
    else:
        if selected_artifact.endswith(".yaml"):
            payload = yaml.safe_load(artifact_text)
            st.json(payload)
        else:
            payload = json.loads(artifact_text)
            st.json(payload)

    st.subheader("Compare Runs")
    compare_candidates = [run_id for run_id in run_id_to_path if run_id != selected_run]
    if compare_candidates:
        compare_run = st.selectbox("Against", ["(none)"] + compare_candidates)
        if compare_run != "(none)":
            _render_comparison(
                artifact_service=artifact_service,
                left_run_dir=run_id_to_path[selected_run],
                right_run_dir=run_id_to_path[compare_run],
            )
    else:
        st.info("Need at least 2 runs to compare")


def _render_comparison(artifact_service, left_run_dir: str, right_run_dir: str) -> None:
    left = artifact_service.load_run_summary(left_run_dir)
    right = artifact_service.load_run_summary(right_run_dir)
    left_report = left.evaluated_report or left.report or {}
    right_report = right.evaluated_report or right.report or {}

    metrics = [
        "completion_rate",
        "acpl_overall",
        "blunder_rate",
        "best_move_agreement",
        "avg_cost_per_game",
        "total_cost_usd",
    ]
    st.dataframe(
        [
            {
                "metric": metric,
                left.run_meta.run_id: left_report.get(metric),
                right.run_meta.run_id: right_report.get(metric),
            }
            for metric in metrics
        ],
        use_container_width=True,
        hide_index=True,
    )
