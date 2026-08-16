"""E2E (opt-in): real opencode provider + real Stockfish engine.

Not part of the default offline suite: requires the local opencode server
and a network-capable account. Run explicitly:

    opencode serve --port 4100 &
    uv run pytest tests/e2e -m e2e -q
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.evaluation import EvaluateRunService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import MetricObservationRepository
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENCODE_SERVER = "http://127.0.0.1:4100"

pytestmark = pytest.mark.e2e


def _opencode_available() -> bool:
    import httpx

    try:
        response = httpx.get(f"{OPENCODE_SERVER}/global/health", timeout=3)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _stockfish_available() -> bool:
    return shutil.which("stockfish") is not None


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    ws = Workspace.from_root(tmp_path / "ws")
    ws.ensure_layout()
    return ws


@pytest.mark.asyncio
async def test_real_opencode_move_selection(workspace: Workspace) -> None:
    """One real move-selection call through the opencode adapter."""
    if not _opencode_available():
        pytest.skip("opencode server not running on 127.0.0.1:4100")
    services = DurableRunServices(workspace, PluginRegistry())
    result = await services.start(
        StartRunCommand(
            manifest_path=REPO_ROOT / "experiments" / "real-opencode-move-selection.yaml"
        ),
        asyncio.Event(),
    )
    assert result.status == "COMPLETED", result
    connection = sqlite3.connect(workspace.data_dir / "state.db")
    committed = connection.execute(
        "SELECT action_json FROM steps WHERE status='COMMITTED'"
    ).fetchall()
    assert len(committed) == 1
    action = committed[0][0]
    assert '"action"' in action, "a real model move must be committed"
    attempts = connection.execute(
        "SELECT status, usage_json, latency_ms FROM attempts WHERE kind='provider'"
    ).fetchall()
    assert attempts, "real provider attempts must be recorded"
    status, usage_raw, latency = attempts[0]
    assert status == "completed"
    import json

    usage = json.loads(usage_raw) if usage_raw else {}
    assert usage.get("input_tokens", 0) > 0, "provider usage must be real"
    assert usage.get("source") == "provider"
    assert latency > 0, "real latency must be measured"


@pytest.mark.asyncio
async def test_real_stockfish_posthoc_evaluation(workspace: Workspace) -> None:
    """Real Stockfish 18 evaluates a fake-backend run post-hoc."""
    if not _stockfish_available():
        pytest.skip("stockfish binary not on PATH")

    services = DurableRunServices(workspace, PluginRegistry())
    run_result = await services.start(
        StartRunCommand(manifest_path=REPO_ROOT / "experiments" / "chess-move-selection.yaml"),
        asyncio.Event(),
    )
    assert run_result.status == "COMPLETED"

    from zgw_eval_stockfish.evaluator import StockfishEvaluator
    from zgw_eval_stockfish.uci import UciEngineClient

    engine = UciEngineClient("stockfish", options={"Threads": "1", "Hash": "16"})
    evaluator = StockfishEvaluator(
        engine,
        limit={"nodes": 20000},
        binary_metadata={
            "binary": "stockfish",
            "binary_sha256": "operator-provided",
        },
    )
    summary = await EvaluateRunService(
        runs=services.runs,
        episodes=services.episodes,
        steps=services.steps,
        metrics=MetricObservationRepository(services.database_engine),
        cas=services.cas,
    ).evaluate(run_result.run_id, evaluator, evaluator_id="evaluator.stockfish")
    assert summary.observations >= 2
    assert "chess.move_class" in summary.metrics
    connection = sqlite3.connect(workspace.data_dir / "state.db")
    rows = connection.execute(
        "SELECT value_text, count(*) FROM metric_observations "
        "WHERE metric_definition_id='chess.move_class' GROUP BY value_text"
    ).fetchall()
    assert rows
    classes = dict(rows)
    # a single-ply move-selection has no predecessor, so CPL is absent ("none");
    # the engine provenance is what matters here.
    assert "none" in classes
    agreement = connection.execute(
        "SELECT value_num FROM metric_observations "
        "WHERE metric_definition_id='chess.best_move_agreement'"
    ).fetchall()
    assert len(agreement) == 1 and agreement[0][0] in (0.0, 1.0)


@pytest.mark.asyncio
async def test_real_full_game_vs_random_legal(workspace: Workspace) -> None:
    """A short real-provider full game (max 4 plies to bound cost)."""
    if not _opencode_available():
        pytest.skip("opencode server not running on 127.0.0.1:4100")
    services = DurableRunServices(workspace, PluginRegistry())
    result = await services.start(
        StartRunCommand(
            manifest_path=REPO_ROOT / "experiments" / "real-opencode-move-selection.yaml"
        ),
        asyncio.Event(),
    )
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_real_multimodal_rgb_move_selection(workspace: Workspace) -> None:
    """One real image+text call through the opencode adapter (gpt-5.6-luna)."""
    if not _opencode_available():
        pytest.skip("opencode server not running on 127.0.0.1:4100")
    services = DurableRunServices(workspace, PluginRegistry())
    result = await services.start(
        StartRunCommand(
            manifest_path=REPO_ROOT / "experiments" / "real-opencode-rgb-move-selection.yaml"
        ),
        asyncio.Event(),
    )
    assert result.status == "COMPLETED", result
    connection = sqlite3.connect(workspace.data_dir / "state.db")
    committed = connection.execute(
        "SELECT action_json FROM steps WHERE status='COMMITTED'"
    ).fetchall()
    assert len(committed) == 1
    action = committed[0][0]
    assert '"action"' in action, "a real multimodal model move must be committed"
    attempts = connection.execute(
        "SELECT status, usage_json FROM attempts WHERE kind='provider'"
    ).fetchall()
    assert attempts, "real provider attempts must be recorded"
    status, usage_raw = attempts[0]
    assert status == "completed"
    usage = json.loads(usage_raw) if usage_raw else {}
    assert usage.get("input_tokens", 0) > 0, "provider usage must be real"
    assert usage.get("source") == "provider"
    artifacts = connection.execute(
        "SELECT relative_path FROM artifacts WHERE media_type='application/vnd.zugzwang.model-request+json'"
    ).fetchall()
    assert artifacts, "canonical request artifact must be recorded"
    request_path = workspace.objects_dir() / artifacts[0][0]
    request_json = json.loads(request_path.read_text())
    image_parts = [
        part
        for message in request_json.get("messages", [])
        for part in message.get("parts", [])
        if part.get("type") == "image"
    ]
    assert image_parts, "canonical request must carry the rendered image part"
    assert image_parts[0]["mime"] == "image/png"
    assert image_parts[0]["data_base64"]
