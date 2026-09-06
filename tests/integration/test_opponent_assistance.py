"""Opponent steps must preserve their observed assistance impacts.

Regression for ZGW-0085/#13 item 4: ``_opponent_step`` computed the opponent's
H/K classes from policy metadata but committed the step row with a hardcoded
``H2/K0``, hiding stronger effective assistance (e.g. engine opponents).
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


class _StubOpponent:
    """Policy opponent that declares engine-level effective assistance."""

    policy_id = "stub.engine-opponent"

    def __init__(self) -> None:
        self.metadata = {"effective_assistance": "H7/K7", "engine": "stub-engine"}

    async def choose(self, state: object, legal_actions: list, seed: int):
        return legal_actions[0]


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "opponent.yaml"
    path.write_text(
        """api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: opponent-assistance-test
  tags: [test, chess]
spec:
  seed: 13
  task:
    plugin: chess.tasks
    config:
      kind: full-game
      max_plies: 2
  players:
    white:
      model:
        backend: fake.backend
        provider: fake
        model: scripted
        strategy: chess.direct
    black:
      policy:
        plugin: chess.random-legal
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
      illegal: 0
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_opponent_step_preserves_declared_assistance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = DeterministicModelBackend(
        rules=(FakeBackendRule(when={"call_index": 0}, output="e2e4"),)
    )
    manifest = _manifest(tmp_path)
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
    monkeypatch.setattr(
        DurableRunCoordinator, "_opponent_for", lambda self, condition: _StubOpponent()
    )
    run_id = await coordinator.start_and_run(resolved, resolved.conditions[0], asyncio.Event())
    await writer.flush()
    await writer.stop()

    connection = sqlite3.connect(workspace.data_dir / "state.db")
    try:
        opponent_steps = connection.execute(
            "SELECT effective_assistance, assistance_violated, action_json FROM steps "
            "WHERE episode_id IN (SELECT episode_id FROM episodes WHERE run_id=?) "
            "AND status='COMMITTED' AND actor_id='stub.engine-opponent'",
            (run_id,),
        ).fetchall()
        assert opponent_steps, "the opponent step must have been committed"
        for effective, violated, action_json in opponent_steps:
            assert effective == "H7/K7", (
                "opponent effective assistance must come from its policy metadata"
            )
            assert violated == 1, "H7 exceeds the declared H2 and must be flagged"
            assert "stub-engine" in action_json
    finally:
        connection.close()
