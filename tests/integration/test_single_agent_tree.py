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
    # ZGW-0085/#14: max_root_branches is honored in the `all` scope, so the
    # configured width (4) caps the twenty legal roots of the start position.
    assert len(decision["selection_rationale"]["root_branches"]) == 4
    assert decision["selection_rationale"]["root_affordance_timing"] == "pre_selection"
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


def _replace(tmp_path: Path, old: str, new: str) -> Path:
    manifest = _manifest(tmp_path)
    contents = manifest.read_text(encoding="utf-8")
    assert old in contents
    manifest.write_text(contents.replace(old, new), encoding="utf-8")
    return manifest


async def _trace_for(tmp_path: Path, manifest: Path) -> tuple[Workspace, str, dict]:
    workspace = Workspace.from_root(tmp_path / "workspace")
    services = DurableRunServices(workspace, PluginRegistry())
    result = await services.start(StartRunCommand(manifest_path=manifest), asyncio.Event())
    assert result.status == "COMPLETED", result.status
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
    return workspace, result.run_id, trace["live_decision"]["decision_trace"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_scope_without_width_config_keeps_affordance_cap(
    tmp_path: Path,
) -> None:
    """Without explicit max_root_branches the all-scope default is unchanged."""
    manifest = _replace(
        tmp_path,
        "        max_root_branches: 4\n",
        "",
    )
    _, _, decision = await _trace_for(tmp_path, manifest)
    assert len(decision["selection_rationale"]["root_branches"]) == 20


@pytest.mark.integration
@pytest.mark.asyncio
async def test_candidate_only_never_exposes_child_replies_before_selection(
    tmp_path: Path,
) -> None:
    """ZGW-0085/#14: candidate_only prepares child replies after the selecting
    call; the prompt must not contain root-branch affordances and the trace
    must label the timing honestly."""
    manifest = _replace(
        tmp_path, "        reply_scope: all\n", "        reply_scope: candidate_only\n"
    )
    workspace, run_id, decision = await _trace_for(tmp_path, manifest)
    rationale = decision["selection_rationale"]
    assert rationale["reply_scope"] == "candidate_only"
    assert rationale["root_affordance_timing"] == "post_selection"
    with sqlite3.connect(workspace.data_dir / "state.db") as connection:
        request_rows = connection.execute(
            "SELECT relative_path FROM artifacts "
            "WHERE media_type='application/vnd.zugzwang.model-request+json' "
            "AND artifact_id IN (SELECT request_artifact_id FROM attempts "
            "WHERE step_id IN (SELECT step_id FROM steps WHERE episode_id IN "
            "(SELECT episode_id FROM episodes WHERE run_id=?)))",
            (run_id,),
        ).fetchall()
    request_text = "\n".join(
        (workspace.objects_dir() / row[0]).read_text(encoding="utf-8") for row in request_rows
    )
    assert "ROOT BRANCH AFFORDANCES" not in request_text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_availability_and_relevance_measured_separately(
    tmp_path: Path,
) -> None:
    """ZGW-0085/#14: the trace separates memory availability from relevance."""
    _, _, decision = await _trace_for(tmp_path, _manifest(tmp_path))
    summary = decision["selection_rationale"]["memory_summary"]
    assert set(summary) >= {
        "available",
        "item_count",
        "position_grounded_count",
        "structured_content_count",
    }
    assert summary["available"] == (summary["item_count"] > 0)
    assert summary["position_grounded_count"] <= summary["item_count"]
