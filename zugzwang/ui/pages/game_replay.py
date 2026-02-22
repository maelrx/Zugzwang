from __future__ import annotations

from typing import Any

import chess
import chess.svg
import streamlit as st
import streamlit.components.v1 as components

from zugzwang.ui.components.metrics import render_kpi_row

try:
    import plotly.express as px
except Exception:  # pragma: no cover - UI optional fallback
    px = None


def render(services: dict[str, Any]) -> None:
    st.title("Game Replay")
    st.caption("Replay move-by-move, inspect metrics, and visualize latency/cost by ply")

    artifact_service = services["artifact_service"]
    replay_service = services["replay_service"]

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

    games = artifact_service.list_games(run_map[selected_run])
    if not games:
        st.warning("No games found for this run")
        return

    game_map = {f"game_{item.game_number:04d}": item.game_number for item in games}
    selected_game = st.selectbox("Game", list(game_map.keys()))

    game = artifact_service.load_game(run_map[selected_run], game_map[selected_game])
    frames = replay_service.build_board_states(game)

    st.subheader("Game Summary")
    render_kpi_row(
        [
            ("Result", game.result),
            ("Termination", game.termination),
            ("Duration (s)", game.duration_seconds),
            ("Cost USD", game.total_cost_usd),
            ("Input tokens", game.total_tokens.get("input", 0)),
            ("Output tokens", game.total_tokens.get("output", 0)),
        ]
    )

    slider_key = f"replay_frame_{selected_run}_{selected_game}"
    max_frame = max(0, len(frames) - 1)
    if slider_key not in st.session_state:
        st.session_state[slider_key] = 0
    st.session_state[slider_key] = min(max_frame, max(0, int(st.session_state[slider_key])))

    nav_left, nav_mid, nav_right = st.columns([1, 2, 2])
    with nav_left:
        orientation = st.selectbox("Orientation", ["white", "black"], index=0)
    with nav_mid:
        if st.button("Previous ply", use_container_width=True):
            st.session_state[slider_key] = max(0, st.session_state[slider_key] - 1)
            st.rerun()
    with nav_right:
        if st.button("Next ply", use_container_width=True):
            st.session_state[slider_key] = min(max_frame, st.session_state[slider_key] + 1)
            st.rerun()

    frame_index = st.slider("Ply", min_value=0, max_value=max_frame, key=slider_key)
    frame = frames[frame_index]

    board = chess.Board(frame.fen)
    board_orientation = chess.WHITE if orientation == "white" else chess.BLACK
    board_svg = chess.svg.board(board=board, orientation=board_orientation, size=430)
    board_html = f"<div style='display:flex;justify-content:center'>{board_svg}</div>"
    components.html(board_html, height=470, scrolling=False)

    st.write(
        f"Ply {frame.ply_number} | Move: {frame.move_san or '-'} ({frame.move_uci or '-'}) | Color: {frame.color or '-'}"
    )

    metrics = replay_service.frame_metrics(game, frame.ply_number)
    st.subheader("Per-ply Metrics")
    render_kpi_row(
        [
            ("tokens_in", metrics.tokens_input),
            ("tokens_out", metrics.tokens_output),
            ("latency_ms", metrics.latency_ms),
            ("retries", metrics.retry_count),
            ("parse_ok", metrics.parse_ok),
            ("legal", metrics.is_legal),
            ("cost_usd", metrics.cost_usd),
        ]
    )
    st.write(f"provider_model: {metrics.provider_model or '-'} | feedback_level: {metrics.feedback_level}")
    if metrics.error:
        st.error(metrics.error)

    st.subheader("Timeline")
    timeline_rows = [
        {
            "ply": int(move.get("ply_number", 0)),
            "latency_ms": float((move.get("move_decision") or {}).get("latency_ms", 0)),
            "cost_usd": float((move.get("move_decision") or {}).get("cost_usd", 0.0)),
        }
        for move in game.moves
    ]
    if timeline_rows:
        if px is not None:
            fig = px.line(timeline_rows, x="ply", y=["latency_ms", "cost_usd"], markers=True)
            fig.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(timeline_rows, x="ply", y=["latency_ms", "cost_usd"])

    st.subheader("Moves")
    st.dataframe(
        [
            {
                "ply": int(move.get("ply_number", 0)),
                "color": move.get("color"),
                "san": (move.get("move_decision") or {}).get("move_san"),
                "uci": (move.get("move_decision") or {}).get("move_uci"),
                "latency_ms": (move.get("move_decision") or {}).get("latency_ms"),
                "cost_usd": (move.get("move_decision") or {}).get("cost_usd"),
            }
            for move in game.moves
        ],
        use_container_width=True,
        hide_index=True,
    )
