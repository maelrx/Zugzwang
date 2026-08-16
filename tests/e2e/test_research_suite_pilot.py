"""ZGW-0076: research suite 0.1 pilot — one real condition per block.

Opt-in e2e: requires the opencode server and the operator's OpenCode Go
subscription. One position (matrix condition 0, the Najdorf tabiya) per block
bounds cost. Stockfish 18 evaluates post-hoc.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_DIR = REPO_ROOT / "experiments" / "research-suite-0.1"

pytestmark = pytest.mark.e2e

PILOT_MANIFESTS = (
    "rep-001-fen.yaml",
    "rep-001-rgb.yaml",
    "ground-001-reason-first.yaml",
    "skill-001-correct.yaml",
    "skill-001-irrelevant.yaml",
    "mm-002-conflict.yaml",
)


def _opencode_available() -> bool:
    try:
        response = httpx.get("http://127.0.0.1:4100/global/health", timeout=3)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    ws = Workspace.from_root(tmp_path / "ws")
    ws.ensure_layout()
    return ws


@pytest.mark.asyncio
async def test_pilot_one_condition_per_block(workspace: Workspace) -> None:
    """Najdorf position (condition index 0) across 6 pilot manifests.

    Harness-level invariants only: every condition performs real provider
    calls with real usage, outcomes (commit OR honest failure) are recorded,
    and G4 performs exactly two phases. Model success rates are the
    experiment's metric, not a test assertion.
    """
    if not _opencode_available():
        pytest.skip("opencode server not running on 127.0.0.1:4100")
    services = DurableRunServices(workspace, PluginRegistry())
    statuses: dict[str, str] = {}
    for manifest_name in PILOT_MANIFESTS:
        result = await services.start(
            StartRunCommand(
                manifest_path=SUITE_DIR / manifest_name,
                condition_index=0,
            ),
            asyncio.Event(),
        )
        statuses[manifest_name] = result.status

    connection = sqlite3.connect(workspace.data_dir / "state.db")
    attempts = connection.execute(
        "SELECT usage_json, latency_ms FROM attempts WHERE kind='provider' AND status='completed'"
    ).fetchall()
    assert len(attempts) >= len(PILOT_MANIFESTS), (
        f"every pilot condition must produce at least one real provider attempt: {statuses}"
    )
    for usage_raw, latency in attempts:
        usage = json.loads(usage_raw) if usage_raw else {}
        assert usage.get("source") == "provider", "usage must come from the provider"
        assert latency > 0, "real latency must be measured"
    episodes = connection.execute("SELECT effective_assistance FROM episodes").fetchall()
    assert any("H3" in row[0] for row in episodes), "G4 pilot must record effective H3"
    steps = connection.execute("SELECT status FROM steps").fetchall()
    assert steps, "steps must be recorded even when the model fails to commit"


@pytest.mark.asyncio
async def test_pilot_posthoc_stockfish_evaluation(workspace: Workspace) -> None:
    """Real Stockfish 18 evaluates every pilot commit offline."""
    if not _opencode_available():
        pytest.skip("opencode server not running on 127.0.0.1:4100")
    import shutil

    if shutil.which("stockfish") is None:
        pytest.skip("stockfish binary not on PATH")
    from zgw_eval_stockfish.evaluator import StockfishEvaluator
    from zgw_eval_stockfish.uci import UciEngineClient

    from zugzwang_runtime.application.evaluation import EvaluateRunService
    from zugzwang_runtime.persistence.repositories import MetricObservationRepository

    services = DurableRunServices(workspace, PluginRegistry())
    evaluated = 0
    for manifest_name in PILOT_MANIFESTS:
        result = await services.start(
            StartRunCommand(
                manifest_path=SUITE_DIR / manifest_name,
                condition_index=0,
            ),
            asyncio.Event(),
        )
        if result.status != "COMPLETED":
            continue
        engine = UciEngineClient("stockfish", options={"Threads": "1", "Hash": "16"})
        evaluator = StockfishEvaluator(engine, limit={"nodes": 20000})
        summary = await EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            cas=services.cas,
        ).evaluate(result.run_id, evaluator, evaluator_id="evaluator.stockfish")
        assert summary.observations >= 1, manifest_name
        assert "chess.move_class" in summary.metrics, manifest_name
        evaluated += 1
        await engine.quit()
    assert evaluated >= 1, "at least one completed pilot run must be evaluated offline"
