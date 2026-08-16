"""R1 (grounded) and R2 (repair) end-to-end tests with the fake backend."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]


def _grounded_manifest(
    tmp_path: Path, strategy: str, encoding: str, parse_retries: int = 0
) -> Path:
    manifest = tmp_path / f"{strategy}-{encoding}.yaml"
    manifest.write_text(
        f"""api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: {strategy}-{encoding}
  tags: [m3, chess, {strategy}]
spec:
  seed: 7
  task:
    plugin: chess.tasks
    config:
      kind: move-selection
      start_fen: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
  players:
    white:
      model:
        backend: fake.backend
        provider: fake
        model: scripted
        strategy: {strategy}
    black:
      policy:
        plugin: fake.stay
  protocol:
    declared_assistance: H3
    declared_knowledge: K0
    observation:
      position: {{fen: true}}
      side_to_move: true
      legal_actions: {{exposure: always, encoding: {encoding}}}
      history: {{mode: none}}
    retries:
      transport: 0
      parse: {parse_retries}
      illegal: 0
  budget:
    max_calls: 20
  evaluation: []
  artifacts:
    raw_requests: true
    raw_responses: true
    redact: standard
""",
        encoding="utf-8",
    )
    return manifest


@pytest.mark.integration
class TestGroundedAndRepair:
    @pytest.fixture
    def workspace(self, tmp_path) -> Workspace:
        ws = Workspace.from_root(tmp_path / "ws")
        ws.ensure_layout()
        return ws

    @pytest.mark.asyncio
    async def test_grounded_opaque_index_roundtrip(self, workspace: Workspace, tmp_path) -> None:
        """R1 with opaque indices: the fake answers '0', resolved to a legal UCI move."""
        from zugzwang_runtime.application.commands import ResolveExperimentCommand
        from zugzwang_runtime.application.services import ResolveExperimentService
        from zugzwang_runtime.artifacts.cas import ContentAddressedStore
        from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
        from zugzwang_runtime.execution.rate_limiting import RateLimiter
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            ArtifactRepository,
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

        manifest = _grounded_manifest(tmp_path, "chess.grounded", "opaque_index")
        ws = Workspace.from_root(tmp_path / "opaque-ws")
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
            artifacts_repo=ArtifactRepository(engine),
        )
        await writer.start()
        backend = DeterministicModelBackend(
            rules=(FakeBackendRule(when={"fingerprint_contains": "chess-grounded"}, output="0"),)
        )
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(manifest_path=manifest)
        )
        coordinator = DurableRunCoordinator(
            registry=PluginRegistry(),
            backend=backend,
            writer=writer,
            event_sink=PersistentEventSink(EventRepository(engine), writer),
            artifact_store=ContentAddressedStore(ws.objects_dir()),
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
        action = connection.execute(
            "SELECT action_json FROM steps WHERE status='COMMITTED'"
        ).fetchone()[0]
        assert action.startswith('{"action": "')

    @pytest.mark.asyncio
    async def test_grounded_uci(self, workspace: Workspace, tmp_path) -> None:
        manifest = _grounded_manifest(tmp_path, "chess.grounded", "uci")
        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(StartRunCommand(manifest_path=manifest), asyncio.Event())
        assert result.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_repair_recovers_after_parse_error(self, workspace: Workspace, tmp_path) -> None:
        """R2: first answer is garbage, second is a legal move (one repair)."""
        from zugzwang_runtime.application.commands import ResolveExperimentCommand
        from zugzwang_runtime.application.services import ResolveExperimentService
        from zugzwang_runtime.artifacts.cas import ContentAddressedStore
        from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
        from zugzwang_runtime.execution.rate_limiting import RateLimiter
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            ArtifactRepository,
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

        manifest = _grounded_manifest(tmp_path, "chess.repair", "uci", parse_retries=1)
        ws = Workspace.from_root(tmp_path / "repair-ws")
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
            artifacts_repo=ArtifactRepository(engine),
        )
        await writer.start()
        sink = PersistentEventSink(EventRepository(engine), writer)
        backend = DeterministicModelBackend(
            rules=(
                FakeBackendRule(when={"call_index_modulo": [2, 0]}, output="not-a-move at all"),
                FakeBackendRule(when={"call_index_modulo": [2, 1]}, output="e2e4"),
            )
        )
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(manifest_path=manifest)
        )
        coordinator = DurableRunCoordinator(
            registry=PluginRegistry(),
            backend=backend,
            writer=writer,
            event_sink=sink,
            artifact_store=ContentAddressedStore(ws.objects_dir()),
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
            "SELECT action_json FROM steps WHERE status='COMMITTED'"
        ).fetchall()
        assert len(committed) == 1
        assert committed[0][0] == '{"action": "e2e4"}'
        attempts = connection.execute(
            "SELECT count(*) FROM attempts WHERE status='completed'"
        ).fetchone()[0]
        assert attempts == 2, "both repair attempts must be recorded"


@pytest.mark.integration
class TestStructuredR3:
    @pytest.mark.asyncio
    async def test_structured_strategy_end_to_end(self, tmp_path) -> None:
        """R3: one structured JSON response with candidates and chosen move."""
        from zugzwang_runtime.application.commands import ResolveExperimentCommand
        from zugzwang_runtime.application.services import ResolveExperimentService
        from zugzwang_runtime.artifacts.cas import ContentAddressedStore
        from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
        from zugzwang_runtime.execution.rate_limiting import RateLimiter
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            ArtifactRepository,
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

        manifest = _grounded_manifest(tmp_path, "chess.structured", "uci")
        ws = Workspace.from_root(tmp_path / "r3-ws")
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
            artifacts_repo=ArtifactRepository(engine),
        )
        await writer.start()
        backend = DeterministicModelBackend(
            rules=(
                FakeBackendRule(
                    when={"fingerprint_contains": "chess-structured"},
                    output=json.dumps(
                        {
                            "analysis": "e4 opens the center",
                            "candidates": [
                                {"move": "e2e4", "score": 0.3},
                                {"move": "g1f3", "score": 0.1},
                            ],
                            "chosen_move": "g1f3",
                        }
                    ),
                ),
            )
        )
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(manifest_path=manifest)
        )
        coordinator = DurableRunCoordinator(
            registry=PluginRegistry(),
            backend=backend,
            writer=writer,
            event_sink=PersistentEventSink(EventRepository(engine), writer),
            artifact_store=ContentAddressedStore(ws.objects_dir()),
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
            "SELECT action_json FROM steps WHERE status='COMMITTED'"
        ).fetchall()
        assert len(committed) == 1
        assert committed[0][0] == '{"action": "g1f3"}'
