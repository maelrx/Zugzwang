"""Chess integration: durable runs of move-selection and full-game with fakes."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]

WHITE_SCRIPT = ("g1f3", "g2g3", "f1g2", "e2e4", "e1g1", "d2d4")


@pytest.mark.integration
class TestChessRuns:
    @pytest.fixture
    def workspace(self, tmp_path) -> Workspace:
        ws = Workspace.from_root(tmp_path / "ws")
        ws.ensure_layout()
        return ws

    async def _run(
        self,
        workspace: Workspace,
        manifest: Path,
        script: tuple[str, ...] = ("e2e4",),
    ) -> str:
        from zugzwang_runtime.application.commands import StartRunCommand

        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(StartRunCommand(manifest_path=manifest), asyncio.Event())
        return result.run_id

    @pytest.mark.asyncio
    async def test_move_selection_run(self, workspace: Workspace) -> None:
        manifest = REPO_ROOT / "experiments" / "chess-move-selection.yaml"
        run_id = await self._run(workspace, manifest)
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        steps = connection.execute("SELECT status, action_json FROM steps").fetchall()
        assert len(steps) == 1
        assert steps[0][0] == "COMMITTED"
        assert steps[0][1] == '{"action": "g1f3"}'
        run = connection.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
        assert run[0] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_full_game_against_random_legal(self, workspace: Workspace) -> None:
        manifest = REPO_ROOT / "experiments" / "chess-full-game.yaml"
        run_id = await self._run(workspace, manifest)
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        steps = connection.execute(
            "SELECT actor_id, status, action_json FROM steps ORDER BY ordinal"
        ).fetchall()
        assert steps
        assert all(status == "COMMITTED" for _, status, _ in steps)
        actors = {actor for actor, _, _ in steps}
        assert any("fake.backend" in actor for actor in actors), actors
        assert any("chess.random-legal" in actor for actor in actors), actors
        # every action must be legal at its position — enforced by the
        # environment; committing proves legality (NFR-001).
        run = connection.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
        assert run[0] == "COMPLETED"
        # 8 plies cap: 4 model + 4 opponent steps
        assert len(steps) == 8

    @pytest.mark.asyncio
    async def test_illegal_model_move_fails_episode(self, tmp_path) -> None:
        """The environment rejects an illegal model move (never applied)."""
        from zugzwang_runtime.application.commands import ResolveExperimentCommand
        from zugzwang_runtime.application.services import ResolveExperimentService
        from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
        from zugzwang_runtime.execution.rate_limiting import RateLimiter
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            AttemptRepository,
            CheckpointRepository,
            EpisodeRepository,
            EventRepository,
            MetricObservationRepository,
            RunRepository,
            SchemaManager,
            StepRepository,
        )
        from zugzwang_runtime.persistence.writer import PersistenceWriter

        ws = Workspace.from_root(tmp_path / "ws")
        ws.ensure_layout()
        db = Database(ws.data_dir / "state.db")
        engine = db.open()
        SchemaManager(engine).upgrade()
        writer = PersistenceWriter(
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            attempts=AttemptRepository(engine),
            events=EventRepository(engine),
            metrics=MetricObservationRepository(engine),
            checkpoints=CheckpointRepository(engine),
        )
        await writer.start()
        sink = PersistentEventSink(EventRepository(engine), writer)
        backend = DeterministicModelBackend(
            rules=(FakeBackendRule(when={"fingerprint_contains": "chess-direct"}, output="e2e5"),)
        )
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(
                manifest_path=REPO_ROOT / "experiments" / "chess-move-selection.yaml"
            )
        )
        coordinator = DurableRunCoordinator(
            registry=PluginRegistry(),
            backend=backend,
            writer=writer,
            event_sink=sink,
            artifact_store=ws.objects_dir()
            and __import__(
                "zugzwang_runtime.artifacts.cas", fromlist=["ContentAddressedStore"]
            ).ContentAddressedStore(ws.objects_dir()),
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            checkpoints=CheckpointRepository(engine),
            rate_limiter=RateLimiter(),
        )
        await coordinator.start_and_run(resolved, resolved.conditions[0], asyncio.Event())
        await writer.flush()
        await writer.stop()
        connection = sqlite3.connect(ws.data_dir / "state.db")
        committed = connection.execute(
            "SELECT count(*) FROM steps WHERE status='COMMITTED'"
        ).fetchone()[0]
        assert committed == 0, "illegal action must never be applied"
        failed = connection.execute(
            "SELECT count(*) FROM episodes WHERE status='FAILED'"
        ).fetchone()[0]
        assert failed == 1
