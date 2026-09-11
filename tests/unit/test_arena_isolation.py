from __future__ import annotations

import asyncio
import json
from pathlib import Path

from zgw_provider_codex_cli.adapter import CodexCliBackend

from tests.contract.test_codex_cli_adapter import _write_fake_codex
from tests.unit.test_arena_play import MODEL_REF
from zugzwang_cli.arena.loop import ArenaDecisionLoop
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
