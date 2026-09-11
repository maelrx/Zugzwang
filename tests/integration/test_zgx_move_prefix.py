"""ZGX wave 1 regression — move-selection MUST apply the declared move_prefix.

The first wave launch played every S12 position from the INITIAL position
because _run_episode only applied ``move_prefix`` for state-reconstruction.
This test replays a 2-ply prefix through the full durable stack and asserts
the episode's initial state is the position AFTER the prefix (and not the
start position).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

import chess
import pytest

pytestmark = pytest.mark.integration

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
PREFIX = ["e2e4", "e7e6"]

MANIFEST = """api_version: zgw.dev/v1alpha1
kind: Experiment
metadata:
  name: zgx-prefix-regression
  tags: [test, regression]
spec:
  seed: 7
  task:
    plugin: chess.tasks
    config:
      kind: move-selection
      start_fen: {start}
      move_prefix: [{prefix}]
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
      illegal: 0
  budget:
    max_calls: 6
    max_concurrent_episodes: 1
  evaluation: []
  artifacts:
    raw_requests: true
    raw_responses: true
"""


def _expected_fen() -> str:
    board = chess.Board()
    for uci in PREFIX:
        board.push(chess.Move.from_uci(uci))
    return board.fen()


def test_move_selection_applies_move_prefix(tmp_path) -> None:
    from zugzwang_runtime.application.commands import StartRunCommand
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.execution.registry import PluginRegistry
    from zugzwang_runtime.workspace import Workspace

    manifest = tmp_path / "prefix.yaml"
    manifest.write_text(MANIFEST.format(start=START, prefix=", ".join(PREFIX)), encoding="utf-8")
    workspace = Workspace.from_root(tmp_path / "ws", wal_policy="ephemeral")
    workspace.ensure_layout()
    services = DurableRunServices(workspace, PluginRegistry())
    result = asyncio.run(services.start(StartRunCommand(manifest_path=manifest), asyncio.Event()))
    assert result.status == "COMPLETED", result

    conn = sqlite3.connect(workspace.data_dir / "state.db")
    try:
        (relative_path,) = conn.execute(
            "SELECT a.relative_path FROM episodes e "
            "JOIN artifacts a ON a.artifact_id = e.initial_state_artifact_id"
        ).fetchone()
    finally:
        conn.close()
    initial = json.loads((workspace.objects_dir() / relative_path).read_text(encoding="utf-8"))
    assert initial["fen"] == _expected_fen(), (
        "move-selection must replay the declared move_prefix into the episode "
        "initial state — the wave-1 bug played every paired position from the "
        "initial position"
    )
    assert initial["initial_fen"] == START
    assert initial.get("moves") == PREFIX
