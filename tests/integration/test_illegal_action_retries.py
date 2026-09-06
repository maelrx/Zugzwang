"""Durable chess retries for impossible model actions."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import ResolveExperimentCommand
from zugzwang_runtime.application.services import ResolveExperimentService
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
from zugzwang_runtime.execution.rate_limiting import RateLimiter
from zugzwang_runtime.execution.registry import PluginRegistry
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
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]


def _manifest(tmp_path: Path, *, max_plies: str = "1") -> Path:
    path = tmp_path / "retry.yaml"
    path.write_text(
        f"""api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: retry-test
  tags: [test, chess]
spec:
  seed: 9
  task:
    plugin: chess.tasks
    config:
      kind: full-game
      max_plies: {max_plies}
  players:
    white:
      model:
        backend: fake.backend
        provider: fake
        model: scripted
        strategy: chess.direct
    black:
      policy:
        plugin: fake.stay
  protocol:
    declared_assistance: H2
    declared_knowledge: K0
    observation:
      position: {{fen: true}}
      side_to_move: true
      history: {{mode: none}}
    retries:
      transport: 0
      parse: 0
      illegal: 3
  budget:
    max_calls: 10
  evaluation: []
  artifacts:
    raw_requests: false
    raw_responses: false
    redact: standard
""",
        encoding="utf-8",
    )
    return path


async def _run_with_backend(
    tmp_path: Path,
    backend: DeterministicModelBackend,
    manifest: Path,
) -> tuple[Workspace, str]:
    workspace = Workspace.from_root(tmp_path / "workspace", wal_policy="ephemeral")
    workspace.ensure_layout()
    engine = Database(workspace.data_dir / "state.db", wal_policy="ephemeral").open()
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
    resolved = ResolveExperimentService(PluginRegistry()).resolve(
        ResolveExperimentCommand(manifest_path=manifest)
    )
    coordinator = DurableRunCoordinator(
        registry=PluginRegistry(),
        backend=backend,
        writer=writer,
        event_sink=sink,
        artifact_store=ContentAddressedStore(workspace.objects_dir()),
        runs=RunRepository(engine),
        episodes=EpisodeRepository(engine),
        steps=StepRepository(engine),
        checkpoints=CheckpointRepository(engine),
        rate_limiter=RateLimiter(),
    )
    run_id = await coordinator.start_and_run(resolved, resolved.conditions[0], asyncio.Event())
    await writer.flush()
    await writer.stop()
    return workspace, run_id


@pytest.mark.integration
class TestIllegalActionRetries:
    @pytest.mark.asyncio
    async def test_retries_same_step_until_legal(self, tmp_path: Path) -> None:
        backend = DeterministicModelBackend(
            rules=(
                FakeBackendRule(when={"call_index": 0}, output="e2e5"),
                FakeBackendRule(when={"call_index": 1}, output="e2e4"),
            )
        )
        manifest = _manifest(tmp_path)
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "raw_requests: false", "raw_requests: true"
            ),
            encoding="utf-8",
        )
        workspace, run_id = await _run_with_backend(tmp_path, backend, manifest)
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        step = connection.execute(
            "SELECT status, action_json FROM steps WHERE episode_id IN "
            "(SELECT episode_id FROM episodes WHERE run_id=?)",
            (run_id,),
        ).fetchone()
        assert step == ("COMMITTED", '{"action": "e2e4"}')
        retries = connection.execute(
            "SELECT count(*) FROM events WHERE run_id=? AND event_type=?",
            (run_id, "step.illegal_action_rejected"),
        ).fetchone()[0]
        assert retries == 1
        request_rows = connection.execute(
            "SELECT relative_path FROM artifacts "
            "WHERE media_type='application/vnd.zugzwang.model-request+json'"
        ).fetchall()
        request_text = "\n".join(
            (workspace.objects_dir() / row[0]).read_text(encoding="utf-8") for row in request_rows
        )
        assert "The formal result was ILLEGAL" in request_text
        assert "Legal moves:" not in request_text

    @pytest.mark.asyncio
    async def test_stops_after_fourth_consecutive_illegal_action(self, tmp_path: Path) -> None:
        backend = DeterministicModelBackend(
            rules=tuple(FakeBackendRule(when={"call_index": i}, output="e2e5") for i in range(4))
        )
        workspace, run_id = await _run_with_backend(tmp_path, backend, _manifest(tmp_path))
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        assert (
            connection.execute(
                "SELECT count(*) FROM steps WHERE status='COMMITTED' AND episode_id IN "
                "(SELECT episode_id FROM episodes WHERE run_id=?)",
                (run_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM events WHERE run_id=? AND event_type=?",
                (run_id, "step.illegal_action_rejected"),
            ).fetchone()[0]
            == 4
        )
        assert (
            connection.execute("SELECT outcome FROM episodes WHERE run_id=?", (run_id,)).fetchone()[
                0
            ]
            == "failed"
        )

    @pytest.mark.asyncio
    async def test_enumerated_retry_is_recorded_as_h3_violation(self, tmp_path: Path) -> None:
        backend = DeterministicModelBackend(
            rules=(
                FakeBackendRule(when={"call_index": 0}, output="e2e5"),
                FakeBackendRule(when={"call_index": 1}, output="e2e4"),
            )
        )
        manifest = _manifest(tmp_path)
        contents = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            contents.replace(
                "    retries:\n      transport: 0\n      parse: 0\n      illegal: 3\n",
                "    retry_profile: enumerate_after_failure\n"
                "    retries:\n      transport: 0\n      parse: 0\n      illegal: 3\n      feedback: enumerated\n",
            ),
            encoding="utf-8",
        )
        workspace, run_id = await _run_with_backend(tmp_path, backend, manifest)
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        assert connection.execute(
            "SELECT effective_assistance, assistance_violated FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone() == ("H3/K0", 1)
        assert connection.execute(
            "SELECT assistance_violated FROM steps WHERE status='COMMITTED'"
        ).fetchone() == (1,)

    def test_null_max_plies_means_terminal_only(self, tmp_path: Path) -> None:
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(manifest_path=_manifest(tmp_path, max_plies="null"))
        )
        coordinator = object.__new__(DurableRunCoordinator)
        assert coordinator._max_steps_for(resolved.conditions[0], "full-game") is None
