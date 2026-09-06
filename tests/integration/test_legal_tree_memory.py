"""Durable integration for R7 legal-tree and episode memory modes."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.trace import TraceStepService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import AttemptRepository, MetricObservationRepository
from zugzwang_runtime.workspace import Workspace


def _manifest(tmp_path: Path, *, mode: str, knowledge: str) -> Path:
    path = tmp_path / f"r7-{mode}.yaml"
    path.write_text(
        f"""api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: r7-legal-tree-{mode}
  tags: [m6, chess, r7, memory-{mode}]
spec:
  seed: 20260904
  task:
    plugin: chess.tasks
    config:
      kind: full-game
      start_fen: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
      model_color: white
      max_plies: 4
      search:
        max_nodes: 16
        max_depth_plies: 2
        max_validation_queries: 32
        max_transition_queries: 16
        max_root_branches: 2
        memory_mode: {mode}
  players:
    white:
      model:
        backend: fake.backend
        provider: fake
        model: scripted
        strategy: chess.legal_tree_memory
    black:
      policy:
        plugin: chess.random-legal
  protocol:
    declared_assistance: H4
    declared_knowledge: {knowledge}
    observation:
      position: {{fen: true}}
      side_to_move: true
      move_number: true
      history: {{mode: full, notation: uci}}
      legal_actions: {{exposure: delayed, encoding: uci}}
    legality:
      validation: {{enabled: true, feedback: enumerated}}
      enumerate: {{enabled: false}}
      transition_sandbox: true
      limits: {{validations: 32, transitions: 16, depth_plies: 2, branch_states: 16}}
    retry_profile: no_retry
    retries: {{transport: 0, parse: 0, illegal: 0}}
  budget:
    max_calls: 6
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
@pytest.mark.parametrize(("mode", "knowledge"), (("episodic", "K0"), ("persistent", "K6")))
async def test_r7_durable_trace_records_legal_tree_and_memory_mode(
    tmp_path: Path, mode: str, knowledge: str
) -> None:
    workspace = Workspace.from_root(tmp_path / "workspace", wal_policy="ephemeral")
    services = DurableRunServices(workspace, PluginRegistry())

    result = await services.start(
        StartRunCommand(manifest_path=_manifest(tmp_path, mode=mode, knowledge=knowledge)),
        asyncio.Event(),
    )

    assert result.status == "COMPLETED"
    episode = services.episodes.for_run(result.run_id)[0]
    steps = services.steps.for_episode(episode["episode_id"])
    assert len(steps) == 4

    trace_service = TraceStepService(
        runs=services.runs,
        steps=services.steps,
        attempts=AttemptRepository(services.database_engine),
        events=services.events,
        metrics=MetricObservationRepository(services.database_engine),
        cas=services.cas,
    )
    model_traces = [
        trace_service.trace(step["step_id"])["live_decision"]["decision_trace"]
        for step in steps
        if step["actor_id"].startswith("fake/")
        or step["actor_id"] == "fake:scripted"
        or "fake" in step["actor_id"]
    ]
    assert len(model_traces) == 2
    first, second = model_traces
    assert first["strategy"]["regime"] == "R7"
    assert first["selection_rationale"]["legal_action_set"]["count"] > 0
    assert first["selection_rationale"]["variant_branches"]
    assert first["selection_rationale"]["memory_mode"] == mode
    assert len(first["calls"]) == 3
    assert all(
        "LEGAL ROOT MOVES" in attempt["request"]["messages"][0]["parts"][0]["text"]
        for attempt in trace_service.trace(steps[0]["step_id"])["live_decision"]["attempts"]
    )
    if mode == "persistent":
        assert second["selection_rationale"]["retrieved_memory"]
    else:
        assert second["selection_rationale"]["retrieved_memory"] == []

    with sqlite3.connect(workspace.data_dir / "state.db") as connection:
        search_sessions = connection.execute(
            "SELECT count(*) FROM search_sessions WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()[0]
        retrieval_events = connection.execute(
            "SELECT count(*) FROM search_retrieval_events WHERE search_session_id IN "
            "(SELECT search_session_id FROM search_sessions WHERE run_id = ?)",
            (result.run_id,),
        ).fetchone()[0]
        session_stats = connection.execute(
            "SELECT stats_json FROM search_sessions WHERE run_id = ?",
            (result.run_id,),
        ).fetchall()
        node_count = connection.execute(
            "SELECT count(*) FROM search_nodes WHERE search_session_id IN "
            "(SELECT search_session_id FROM search_sessions WHERE run_id = ?)",
            (result.run_id,),
        ).fetchone()[0]
        edge_count = connection.execute(
            "SELECT count(*) FROM search_edges WHERE search_session_id IN "
            "(SELECT search_session_id FROM search_sessions WHERE run_id = ?)",
            (result.run_id,),
        ).fetchone()[0]
    assert search_sessions == 2
    assert retrieval_events == 18
    assert node_count == sum(json.loads(row[0])["nodes"] for row in session_stats)
    assert edge_count == sum(json.loads(row[0])["edges"] for row in session_stats)
