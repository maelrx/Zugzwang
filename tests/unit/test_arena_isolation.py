from __future__ import annotations

import asyncio
import json
from pathlib import Path

from zgw_provider_codex_cli.adapter import CodexCliBackend

from tests.contract.test_codex_cli_adapter import _write_fake_codex
from tests.unit.test_arena_play import MODEL_REF
from zugzwang_cli.arena.game import ArenaGame
from zugzwang_cli.arena.loop import ArenaDecisionLoop, DecisionOutcome
from zugzwang_cli.arena.positions import BoardFacade


def test_unsafe_native_execution_cannot_commit_and_evidence_survives(tmp_path: Path):
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "stockfish",
                "exit_code": 0,
                "aggregated_output": "bestmove e2e4",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": '{"command":"board_finalize","arguments":{"node_id":"n0","action_id":"e2e4"}}',
            },
        },
    ]
    exe = _write_fake_codex(
        tmp_path, "cat <<'JSONL'\n" + "\n".join(json.dumps(x) for x in events) + "\nJSONL\n"
    )
    records = []
    board = BoardFacade()
    outcome = asyncio.run(
        ArenaDecisionLoop(
            game_id="isolated",
            board=board,
            backend=CodexCliBackend(executable=exe),
            model_ref=MODEL_REF,
            call_sink=records.append,
        ).run()
    )
    assert outcome.status == "PROVIDER_ISOLATION_VIOLATION"
    assert outcome.uci is None and board.moves == []
    assert "command_execution" in json.dumps(records)
    assert len(records) == 1


def _game() -> ArenaGame:
    return ArenaGame(
        game_id="taint-game",
        created_at="2026-09-10T00:00:00",
        setup={"provider": "codex-cli", "model": "gpt-5.6-luna", "human_color": "black"},
        board=BoardFacade(),
    )


def test_isolation_violation_taints_game_and_survives_later_success() -> None:
    game = _game()
    violation = DecisionOutcome(
        status="PROVIDER_ISOLATION_VIOLATION",
        error="Provider isolation violation: native execution 'command_execution'; move rejected.",
    )
    assert game.record_model_outcome(violation, model_color="white") is False
    assert game.isolation_violation is True
    assert game.to_state()["isolation_violation"] is True
    assert game.assistance_violations, "violation record must be persisted"
    assert game.last_error is not None and "isolation" in game.last_error.lower()

    # A later clean move must not erase the security taint.
    committed = DecisionOutcome(status="COMMITTED", uci="e2e4", final_text="1. e4")
    assert game.record_model_outcome(committed, model_color="white") is True
    assert game.isolation_violation is True
    assert game.to_state()["isolation_violation"] is True
    assert game.assistance_violations


def test_taint_round_trips_through_persistence(tmp_path: Path) -> None:
    game = _game()
    game.record_model_outcome(
        DecisionOutcome(status="PROVIDER_ISOLATION_VIOLATION", error="native execution"),
        model_color="white",
    )
    game.dump(tmp_path)
    from zugzwang_cli.arena.game import load_game

    reloaded = load_game(tmp_path / "taint-game.json")
    assert reloaded is not None
    assert reloaded.isolation_violation is True
    assert reloaded.to_state()["isolation_violation"] is True
