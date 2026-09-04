"""Durable integration for the single-agent full-capability tree."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.trace import TraceStepService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import AttemptRepository, MetricObservationRepository
from zugzwang_runtime.workspace import Workspace


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "single-agent-tree.yaml"
    path.write_text(
        """api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: single-agent-tree-wiring
  tags: [m6, chess, r7, single-agent]
spec:
  seed: 20260908
  task:
    plugin: chess.tasks
    config:
      kind: move-selection
      start_fen: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
      search:
        max_nodes: 64
        max_depth_plies: 2
        max_validation_queries: 128
        max_transition_queries: 64
        max_root_branches: 4
        max_affordance_roots: 32
        reply_scope: all
        memory_mode: persistent
  players:
    white:
      model:
        backend: fake.backend
        provider: fake
        model: scripted
        strategy: chess.single_agent_tree
    black:
      policy:
        plugin: fake.stay
  protocol:
    declared_assistance: H4
    declared_knowledge: K6
    observation:
      position: {fen: true}
      side_to_move: true
      move_number: true
      history: {mode: none}
      legal_actions: {exposure: delayed, encoding: uci}
    legality:
      validation: {enabled: true, feedback: enumerated}
      enumerate: {enabled: false}
      transition_sandbox: true
      limits: {validations: 128, transitions: 64, depth_plies: 2, branch_states: 64}
    retry_profile: no_retry
    retries: {transport: 0, parse: 0, illegal: 0}
  budget:
    max_calls: 1
    max_concurrent_episodes: 1
  evaluation: []
  artifacts:
    raw_requests: true
    raw_responses: true
    redact: standard
""",
        encoding="utf-8",
    )
    return path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_agent_tree_persists_one_call_and_all_root_affordances(
    tmp_path: Path,
) -> None:
    workspace = Workspace.from_root(tmp_path / "workspace")
    services = DurableRunServices(workspace, PluginRegistry())

    result = await services.start(
        StartRunCommand(manifest_path=_manifest(tmp_path)), asyncio.Event()
    )

    assert result.status == "COMPLETED"
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
    decision = trace["live_decision"]["decision_trace"]

    assert decision["strategy"]["id"] == "chess.single_agent_tree"
    assert decision["strategy"]["regime"] == "R7"
    assert len(decision["calls"]) == 1
    assert decision["selection_rationale"]["single_agent"] is True
    assert len(decision["selection_rationale"]["root_branches"]) == 20
    assert decision["selection_rationale"]["final_validation"]["legal"] is True

    with sqlite3.connect(workspace.data_dir / "state.db") as connection:
        session = connection.execute(
            "SELECT algorithm, stats_json FROM search_sessions WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()
        retrievals = connection.execute(
            "SELECT count(*) FROM search_retrieval_events WHERE search_session_id IN "
            "(SELECT search_session_id FROM search_sessions WHERE run_id = ?)",
            (result.run_id,),
        ).fetchone()[0]
    assert session is not None
    assert session[0] == "R7-SingleAgentTree"
    assert retrievals == 9
