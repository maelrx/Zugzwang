"""A timeout with unknown outcome must fail closed, never retry via illegal budget.

Regression for ZGW-0085/#13 item 2: decision failures used to be converted into
"no action" and re-entered the provider through the illegal-action retry budget.
"""

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


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "timeout.yaml"
    # illegal: 3 leaves room for the old buggy behavior to retry; the policy
    # under test must still fail on the first unknown-outcome timeout.
    path.write_text(
        """api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: timeout-unknown-test
  tags: [test, chess]
spec:
  seed: 11
  task:
    plugin: chess.tasks
    config:
      kind: full-game
      max_plies: 1
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
      position: {fen: true}
      side_to_move: true
      history: {mode: none}
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


async def _run(
    tmp_path: Path, backend: DeterministicModelBackend, manifest: Path
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


@pytest.mark.fault
@pytest.mark.asyncio
async def test_unknown_outcome_timeout_fails_closed_without_new_call(tmp_path: Path) -> None:
    backend = DeterministicModelBackend(
        rules=(FakeBackendRule(**{"when": {"call_index": 0}, "raise": "timeout"}),)
    )
    workspace, run_id = await _run(tmp_path, backend, _manifest(tmp_path))
    connection = sqlite3.connect(workspace.data_dir / "state.db")
    try:
        attempts = connection.execute(
            "SELECT count(*) FROM attempts WHERE step_id IN "
            "(SELECT step_id FROM steps WHERE episode_id IN "
            "(SELECT episode_id FROM episodes WHERE run_id=?))",
            (run_id,),
        ).fetchone()[0]
        assert attempts == 1, "unknown-outcome timeout must not trigger a new provider call"

        timeout_events = connection.execute(
            "SELECT count(*) FROM events WHERE run_id=? AND event_type='provider.call.timeout_unknown'",
            (run_id,),
        ).fetchone()[0]
        assert timeout_events == 1
        decision_failed = connection.execute(
            "SELECT count(*) FROM events WHERE run_id=? AND event_type='step.decision_failed'",
            (run_id,),
        ).fetchone()[0]
        assert decision_failed == 1
        illegal_rejections = connection.execute(
            "SELECT count(*) FROM events WHERE run_id=? AND event_type='step.illegal_action_rejected'",
            (run_id,),
        ).fetchone()[0]
        assert illegal_rejections == 0, "decision errors must not consume illegal-action retries"

        episode = connection.execute(
            "SELECT status, outcome FROM episodes WHERE run_id=?", (run_id,)
        ).fetchone()
        assert episode == ("FAILED", "decision_error")

        step = connection.execute(
            "SELECT status FROM steps WHERE episode_id IN "
            "(SELECT episode_id FROM episodes WHERE run_id=?)",
            (run_id,),
        ).fetchone()
        assert step == ("TERMINAL_FAILURE",)
    finally:
        connection.close()
