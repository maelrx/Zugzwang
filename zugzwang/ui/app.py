from __future__ import annotations

import os
from typing import Any

import streamlit as st

from zugzwang.infra.env import load_dotenv
from zugzwang.ui.pages import evaluation, game_replay, guided_flow, home, job_monitor, run_explorer, run_lab
from zugzwang.ui.pages.future_placeholder import render as render_future_placeholder
from zugzwang.ui.services import ArtifactService, ConfigService, EvaluationService, ReplayService, RunService


CAPABILITY_REGISTRY = {
    "strategy_inspector": False,
    "retrieval_inspector": False,
    "agent_trace": False,
    "scheduler": False,
    "research_dashboard": False,
}

FUTURE_PAGE_CONFIG = {
    "Strategy Inspector": (
        "strategy_inspector",
        "Phase 3 hook: prompt/context/validator traces and retry analytics.",
    ),
    "Retrieval Inspector": (
        "retrieval_inspector",
        "Phase 4 hook: retrieval chunks, latency and hit-rate per phase.",
    ),
    "Agent Trace": (
        "agent_trace",
        "Phase 5 hook: MoA sub-calls, arbitration and aggregator rationale.",
    ),
    "Scheduler": (
        "scheduler",
        "Phase 6 hook: queue, priority, pause/resume and batch orchestration.",
    ),
    "Research Dashboard": (
        "research_dashboard",
        "Phase 7 hook: publication-grade plots and exports.",
    ),
}


@st.cache_resource
def _build_services() -> dict[str, Any]:
    load_dotenv()
    return {
        "config_service": ConfigService(),
        "run_service": RunService(),
        "evaluation_service": EvaluationService(),
        "artifact_service": ArtifactService(),
        "replay_service": ReplayService(),
        "capabilities": CAPABILITY_REGISTRY,
    }


def _render_sidebar(services: dict[str, Any], page_options: list[str]) -> str:
    st.sidebar.title("Zugzwang")
    st.sidebar.caption("Local single-user GUI")

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Guided Flow"

    selected = st.sidebar.radio("Pages", page_options, key="nav_page")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Environment")
    zai_set = bool(os.environ.get("ZAI_API_KEY", "").strip())
    stockfish_path = os.environ.get("STOCKFISH_PATH", "")
    stockfish_ok = bool(stockfish_path.strip()) and os.path.exists(stockfish_path)
    st.sidebar.write(f"ZAI_API_KEY: {'set' if zai_set else 'missing'}")
    st.sidebar.write(f"STOCKFISH_PATH: {'found' if stockfish_ok else 'fallback/PATH'}")

    artifact_service = services["artifact_service"]
    run_service = services["run_service"]

    runs = artifact_service.list_runs(filters=None)
    jobs = run_service.list_jobs(refresh=True)
    running = sum(1 for job in jobs if job.get("status") == "running")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Current State")
    st.sidebar.write(f"Runs: {len(runs)}")
    st.sidebar.write(f"Jobs running: {running}")

    selected_run = st.session_state.get("selected_run_id")
    if isinstance(selected_run, str) and selected_run.strip():
        st.sidebar.write(f"Selected run: {selected_run}")

    st.sidebar.markdown("---")
    st.sidebar.caption("Recommended flow: Guided Flow -> Run Lab -> Job Monitor -> Replay/Evaluation")
    return selected


def main() -> None:
    st.set_page_config(
        page_title="Zugzwang GUI",
        page_icon="Z",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    services = _build_services()
    capabilities = services["capabilities"]
    page_options = [
        "Guided Flow",
        "Home",
        "Run Lab",
        "Job Monitor",
        "Run Explorer",
        "Game Replay",
        "Evaluation",
        *list(FUTURE_PAGE_CONFIG.keys()),
    ]

    selected = _render_sidebar(services, page_options)

    if selected == "Guided Flow":
        guided_flow.render(services)
        return
    if selected == "Home":
        home.render(services)
        return
    if selected == "Run Lab":
        run_lab.render(services)
        return
    if selected == "Job Monitor":
        job_monitor.render(services)
        return
    if selected == "Run Explorer":
        run_explorer.render(services)
        return
    if selected == "Game Replay":
        game_replay.render(services)
        return
    if selected == "Evaluation":
        evaluation.render(services)
        return

    capability_key, description = FUTURE_PAGE_CONFIG[selected]
    if not capabilities.get(capability_key, False):
        render_future_placeholder(
            selected,
            f"{description} Capability '{capability_key}' is disabled in this build.",
        )
        return
    render_future_placeholder(selected, description)


if __name__ == "__main__":
    main()
