from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

import streamlit as st

from zugzwang.ui.components.metrics import render_kpi_row


def render(services: dict[str, Any]) -> None:
    st.title("Evaluation")
    st.caption("Run Stockfish-based evaluation and inspect quality metrics")

    artifact_service = services["artifact_service"]
    evaluation_service = services["evaluation_service"]

    runs = artifact_service.list_runs(filters=None)
    if not runs:
        st.info("No runs available")
        return

    run_map = {run.run_id: run.run_dir for run in runs}
    run_ids = list(run_map.keys())

    selected_run_default = st.session_state.get("selected_run_id")
    default_index = run_ids.index(selected_run_default) if selected_run_default in run_ids else 0
    selected_run = st.selectbox("Run", run_ids, index=default_index)
    st.session_state["selected_run_id"] = selected_run

    summary = artifact_service.load_run_summary(run_map[selected_run])

    stockfish_hint = _stockfish_hint(summary.resolved_config)
    if stockfish_hint["level"] == "error":
        st.error(stockfish_hint["message"])
    elif stockfish_hint["level"] == "warning":
        st.warning(stockfish_hint["message"])
    else:
        st.success(stockfish_hint["message"])

    can_evaluate = stockfish_hint["level"] != "error"

    with st.form("evaluation_form"):
        player_color = st.selectbox("Player color", ["black", "white"], index=0)
        opponent_elo_raw = st.text_input("Opponent Elo (optional)", value="")
        output_filename = st.text_input("Output filename", value="experiment_report_evaluated.json")
        submitted = st.form_submit_button("Start Evaluation", use_container_width=True, disabled=not can_evaluate)

    if submitted:
        opponent_elo = _parse_float(opponent_elo_raw)
        handle = evaluation_service.start_evaluation(
            run_dir=run_map[selected_run],
            player_color=player_color,
            opponent_elo=opponent_elo,
            output_filename=output_filename,
        )
        st.session_state["evaluation_last_job_id"] = handle.job_id
        st.success(f"Evaluation job launched: {handle.job_id}")

    job_id = st.session_state.get("evaluation_last_job_id")
    if isinstance(job_id, str) and job_id.strip():
        st.subheader("Latest Evaluation Job")
        result = evaluation_service.get_evaluation_result(job_id)
        render_kpi_row(
            [
                ("job_id", job_id),
                ("status", result.status),
                ("output_report", result.output_report),
            ]
        )
        if result.payload:
            with st.expander("Evaluation payload", expanded=False):
                st.json(result.payload)
        with st.expander("Logs", expanded=False):
            st.code(result.log_tail or "(no logs)")

        if result.status == "running":
            time.sleep(2)
            st.rerun()

    st.subheader("Current Reports")
    if summary.report:
        with st.expander("experiment_report.json", expanded=False):
            st.json(summary.report)

    if summary.evaluated_report:
        with st.expander("experiment_report_evaluated.json", expanded=True):
            st.json(summary.evaluated_report)
        _render_evaluation_snapshot(summary.evaluated_report)
    else:
        st.info("No evaluated report found yet for this run")


def _render_evaluation_snapshot(report: dict[str, Any]) -> None:
    st.subheader("Evaluated Metrics Snapshot")
    render_kpi_row(
        [
            ("ACPL", report.get("acpl_overall")),
            ("Blunder rate", report.get("blunder_rate")),
            ("Best move agreement", report.get("best_move_agreement")),
            ("Elo estimate", report.get("elo_estimate")),
        ]
    )


def _stockfish_hint(resolved_config: dict[str, Any] | None) -> dict[str, str]:
    configured_path = None
    if isinstance(resolved_config, dict):
        eval_cfg = resolved_config.get("evaluation", {})
        if isinstance(eval_cfg, dict):
            stock_cfg = eval_cfg.get("stockfish", {})
            if isinstance(stock_cfg, dict):
                configured_path = stock_cfg.get("path")

    env_path = os.environ.get("STOCKFISH_PATH")
    if isinstance(configured_path, str) and configured_path.strip():
        if Path(configured_path).exists():
            return {"level": "ok", "message": f"Stockfish path found in config: {configured_path}"}
        return {"level": "error", "message": f"Stockfish path from config is missing: {configured_path}"}

    if isinstance(env_path, str) and env_path.strip():
        if Path(env_path).exists():
            return {"level": "ok", "message": f"Stockfish path found in env: {env_path}"}
        return {"level": "error", "message": f"STOCKFISH_PATH is set but missing: {env_path}"}

    path_binary = shutil.which("stockfish")
    if path_binary:
        return {"level": "warning", "message": f"Using stockfish from PATH: {path_binary}"}

    return {
        "level": "error",
        "message": "Stockfish binary not found. Set STOCKFISH_PATH or install stockfish on PATH.",
    }


def _parse_float(raw: str) -> float | None:
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None
