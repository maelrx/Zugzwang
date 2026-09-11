"""Turn projection and loop observation never change chess decisions."""

from __future__ import annotations

import json
import time
from pathlib import Path

from tests.unit.test_arena_play import MODEL_REF, ScriptedBackend, _provider_result, _tool_call
from zugzwang_cli.arena.game import load_game
from zugzwang_cli.arena.loop import ArenaDecisionLoop
from zugzwang_cli.arena.positions import BoardFacade
from zugzwang_cli.arena.progress import new_progress, project_event
from zugzwang_cli.arena.server import ArenaService
from zugzwang_core.ports.model import ReasoningTelemetry


def test_projection_replaces_stream_updates_and_separates_rounds() -> None:
    state = new_progress(6, streaming=True)
    for text in ["First", "Updated"]:
        project_event(state, {"kind": "summary", "round": 1, "id": "s", "text": text})
    project_event(state, {"kind": "summary", "round": 2, "id": "s", "text": "Second round"})
    assert [s["text"] for s in state["summaries"]] == ["Updated", "Second round"]
    assert [s["round"] for s in state["summaries"]] == [1, 2]
    assert new_progress(6, streaming=False)["summaries"] == []


async def test_loop_receives_summary_while_awaiting_provider_and_drops_raw_telemetry() -> None:
    rows = []

    class Backend:
        async def infer_with_progress(self, request, context, sink):
            sink({"id": "s", "text": "A short provider summary.", "source": "codex-cli"})
            assert rows[-1]["kind"] == "summary"
            result = _provider_result(
                request, (_tool_call("board_finalize", {"node_id": "n0", "action_id": "e2e4"}),)
            )
            return result.model_copy(
                update={
                    "reasoning_telemetry": ReasoningTelemetry(
                        provider="test",
                        model="test",
                        reasoning_summary="RAW",
                        reasoning_items=({"type": "reasoning", "text": "RAW"},),
                    )
                }
            )

    outcome = await ArenaDecisionLoop(
        game_id="test",
        board=BoardFacade(),
        backend=Backend(),
        model_ref=MODEL_REF,
        progress_sink=rows.append,
    ).run()
    assert outcome.uci == "e2e4"
    assert [r["kind"] for r in rows] == ["preparing", "waiting", "summary", "received", "selected"]
    assert "RAW" not in json.dumps(rows)


def test_progress_persists_and_new_turn_resets(tmp_path: Path) -> None:
    backend = ScriptedBackend(
        [[_tool_call("board_finalize", {"node_id": "n0", "action_id": "e7e5"})]]
    )
    service = ArenaService(tmp_path, backend_factory=lambda *a, **k: backend)
    game = service.create_game({"provider": "codex-cli", "human_color": "white"})
    service.apply_move(game.game_id, "e2e4")
    for _ in range(300):
        if game.status != "model_thinking":
            break
        time.sleep(0.01)
    assert game.status == "human_turn"
    assert game.model_progress["status"] == "completed"
    restored = load_game(tmp_path / f"{game.game_id}.json")
    assert restored.model_progress == game.model_progress
    assert len(restored.moves) == 2
    assert (tmp_path / f"{game.game_id}-progress.jsonl").exists()


def test_failed_turn_keeps_progress_and_restart_marks_interrupted(tmp_path: Path) -> None:
    from zugzwang_core.domain.errors import ProviderTimeoutError

    service = ArenaService(
        tmp_path,
        backend_factory=lambda *a, **k: ScriptedBackend([ProviderTimeoutError("unknown outcome")]),
    )
    game = service.create_game({"provider": "codex-cli"})
    service.apply_move(game.game_id, "e2e4")
    for _ in range(300):
        if game.status != "model_thinking":
            break
        time.sleep(0.01)
    assert game.model_progress["status"] == "failed"
    assert len(game.moves) == 1
    game.status = "model_thinking"
    game.model_progress = new_progress(6, streaming=True)
    game.dump(tmp_path)
    restored = load_game(tmp_path / f"{game.game_id}.json")
    assert restored.model_progress["status"] == "interrupted"
