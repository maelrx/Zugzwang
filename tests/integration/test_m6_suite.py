"""M6 scientific suite tests: R0-R3 matrix, paired openings, reconstruction."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.evaluation import ReportRunService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import MetricObservationRepository
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    ws = Workspace.from_root(tmp_path / "ws", wal_policy="ephemeral")
    ws.ensure_layout()
    return ws


@pytest.mark.integration
class TestStrategySuite:
    @pytest.mark.asyncio
    async def test_four_regimes_one_backend(self, workspace: Workspace) -> None:
        """R0-R3 over the same fake backend: protocol differences only."""
        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(
            StartRunCommand(manifest_path=REPO_ROOT / "experiments" / "strategy-suite.yaml"),
            asyncio.Event(),
        )
        assert result.status == "COMPLETED"
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        run_rows = connection.execute(
            "SELECT run_id, status FROM runs ORDER BY started_at DESC LIMIT 4"
        ).fetchall()
        assert len(run_rows) == 4
        assert all(status == "COMPLETED" for _, status in run_rows)
        committed = connection.execute(
            "SELECT count(*) FROM steps WHERE status='COMMITTED'"
        ).fetchone()[0]
        assert committed == 4

    @pytest.mark.asyncio
    async def test_paired_openings_structure(self, workspace: Workspace) -> None:
        services = DurableRunServices(workspace, PluginRegistry())
        await services.start(
            StartRunCommand(manifest_path=REPO_ROOT / "experiments" / "paired-openings.yaml"),
            asyncio.Event(),
        )
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        episodes = connection.execute(
            "SELECT config_json, status, outcome FROM episodes ORDER BY ordinal"
        ).fetchall()
        assert len(episodes) == 4, "2 openings x 2 colors"
        assert all(status == "COMPLETED" for _, status, _ in episodes)
        colors = sorted(json_loads(cfg)["model_color"] for cfg, _, _ in episodes)
        assert colors == ["black", "black", "white", "white"]
        openings = sorted(json_loads(cfg)["start_fen"] for cfg, _, _ in episodes)
        assert len(set(openings)) == 2, "two distinct openings"

    @pytest.mark.asyncio
    async def test_state_reconstruction_scoring(self, workspace: Workspace) -> None:
        services = DurableRunServices(workspace, PluginRegistry())
        await services.start(
            StartRunCommand(manifest_path=REPO_ROOT / "experiments" / "state-reconstruction.yaml"),
            asyncio.Event(),
        )
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        scores = connection.execute(
            "SELECT episode_id, payload_json FROM events WHERE payload_json LIKE '%reconstruction_scores%'"
        ).fetchall()
        assert len(scores) == 2
        score_values = {s[0]: json_loads(s[1])["reconstruction_scores"] for s in scores}
        exact_scores = sorted(v["exact_match"] for v in score_values.values())
        assert exact_scores == [0.0, 1.0], "one exact, one wrong prediction"
        wrong = next(v for v in score_values.values() if v["exact_match"] == 0.0)
        assert wrong["piece_square_accuracy"] > 0.9

    @pytest.mark.asyncio
    async def test_suite_report_honest_grouping(self, workspace: Workspace) -> None:
        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(
            StartRunCommand(manifest_path=REPO_ROOT / "experiments" / "strategy-suite.yaml"),
            asyncio.Event(),
        )
        report_service = ReportRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            events=services.events,
        )
        report = report_service.report(result.run_id)
        markdown = report_service.to_markdown(report)
        assert "does not establish" in markdown
        assert report["operational"]["cost_status"] == "unknown"


def json_loads(value: str | None) -> dict:
    import json

    return json.loads(value) if value else {}
