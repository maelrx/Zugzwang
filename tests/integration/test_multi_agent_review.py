"""Durable wiring for the explicit R5 multi-agent review strategy."""

from __future__ import annotations

import asyncio

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.trace import TraceStepService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import AttemptRepository, MetricObservationRepository
from zugzwang_runtime.workspace import Workspace


@pytest.mark.integration
@pytest.mark.asyncio
async def test_durable_run_persists_all_three_multi_agent_roles(tmp_path) -> None:
    manifest = tmp_path / "multi-agent-review.yaml"
    manifest.write_text(
        """api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: multi-agent-review-wiring
  tags: [m6, chess, r5, multi-agent]
spec:
  seed: 11
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
        strategy: chess.multi_agent_review
    black:
      policy:
        plugin: fake.stay
  protocol:
    declared_assistance: H2
    declared_knowledge: K0
    observation:
      position: {fen: true}
      side_to_move: true
      move_number: true
      history: {mode: none}
    retries:
      transport: 0
      parse: 0
      illegal: 0
  budget:
    max_calls: 3
    max_attempts: 1
  evaluation: []
  artifacts:
    raw_requests: true
    raw_responses: true
    redact: standard
""",
        encoding="utf-8",
    )
    workspace = Workspace.from_root(tmp_path / "workspace", wal_policy="ephemeral")
    services = DurableRunServices(workspace, PluginRegistry())

    result = await services.start(StartRunCommand(manifest_path=manifest), asyncio.Event())

    assert result.status == "COMPLETED"
    summary = services.summary(result.run_id)
    assert summary.attempts == 3
    assert summary.events > 0
    episode = services.episodes.for_run(result.run_id)[0]
    step = services.steps.for_episode(episode["episode_id"])[0]
    trace = TraceStepService(
        runs=services.runs,
        steps=services.steps,
        attempts=AttemptRepository(services.database_engine),
        events=services.events,
        metrics=MetricObservationRepository(services.database_engine),
        cas=services.cas,
    ).trace(step["step_id"])

    assert trace["live_decision"]["decision_trace"]["strategy"]["regime"] == "R5"
    assert [call["attempt_id"] for call in trace["live_decision"]["decision_trace"]["calls"]]
    assert trace["live_decision"]["decision_trace"]["selection_rationale"]["workflow"] == [
        "critical_scout",
        "strategy_planner",
        "final_reviewer",
    ]
    assert len(trace["live_decision"]["attempts"]) == 3
    assert all(attempt["request"] is not None for attempt in trace["live_decision"]["attempts"])
