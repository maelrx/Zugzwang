"""Arena auto mode: model vs Stockfish spectator games (live in the webapp)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_arena_play import ScriptedBackend, _tool_call
from zugzwang_cli.arena.loop import ROOT_NODE_ID
from zugzwang_cli.arena.server import ArenaService


def _first_legal(board: Any) -> str:
    # Deterministic offline engine stand-in for tests.
    return next(iter(board.board.legal_moves)).uci()


@pytest.fixture()
def service(tmp_path: Path) -> ArenaService:
    backend = ScriptedBackend(
        [
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e7e5"})],
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e7e6"})],
        ]
    )
    return ArenaService(
        tmp_path,
        backend_factory=lambda *a, **k: backend,
        engine_move=_first_legal,
    )


def _wait(game: Any, predicate: Any, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"condition not met; moves={[m.uci for m in game.moves]}")


def test_engine_starts_when_it_has_white_and_model_answers(service: ArenaService) -> None:
    game = service.create_game(
        {
            "provider": "codex-cli",
            "model": "gpt-6-astra",
            "opponent": "stockfish",
            "human_color": "white",  # engine plays white, model black
        }
    )
    assert game.status == "engine_thinking"
    assert game.to_state()["thinking"] is True
    _wait(game, lambda: len(game.moves) >= 2)
    actors = [move.actor for move in game.moves]
    assert actors[:2] == ["engine", "model"]
    assert game.status in {"engine_thinking", "model_thinking"}  # play continues


def test_engine_runs_after_model_when_model_has_white(tmp_path: Path) -> None:
    backend = ScriptedBackend(
        [[_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e2e4"})]]
    )
    service = ArenaService(
        tmp_path,
        backend_factory=lambda *a, **k: backend,
        engine_move=_first_legal,
    )
    game = service.create_game(
        {
            "provider": "codex-cli",
            "model": "gpt-6-astra",
            "opponent": "stockfish",
            "human_color": "black",  # model white, engine black
        }
    )
    assert game.status == "model_thinking"
    _wait(game, lambda: len(game.moves) >= 2)
    actors = [move.actor for move in game.moves]
    assert actors[0] == "model"
    assert actors[1] == "engine"


def test_human_moves_are_rejected_in_spectator_games(service: ArenaService) -> None:
    game = service.create_game(
        {
            "provider": "codex-cli",
            "model": "gpt-6-astra",
            "opponent": "stockfish",
            "human_color": "white",
        }
    )
    with pytest.raises(ValueError, match=r"spectator|espectador"):
        service.apply_move(game.game_id, "e2e4")


def test_human_games_keep_previous_behavior(service: ArenaService) -> None:
    game = service.create_game({"provider": "codex-cli", "model": "gpt-6-astra"})
    assert game.status == "human_turn"
    assert game.setup.get("opponent", "human") == "human"


def test_spectator_failure_keeps_turn_for_retry(tmp_path: Path) -> None:
    # Regression: a failed model turn in a spectator game must not fall back to
    # "human_turn" (there is no human); the turn stays with the side to retry.
    backend = ScriptedBackend([])  # first infer raises: exhausted script
    service = ArenaService(
        tmp_path,
        backend_factory=lambda *a, **k: backend,
        engine_move=_first_legal,
    )
    game = service.create_game(
        {
            "provider": "codex-cli",
            "model": "gpt-6-astra",
            "opponent": "stockfish",
            "human_color": "white",  # engine plays white, model black
        }
    )
    _wait(game, lambda: game.last_error is not None and game.status != "engine_thinking")
    assert game.status != "human_turn"
    assert game.status == "model_thinking"
    assert game.last_error
    # The retry endpoint re-advances the spectator game instead of refusing.
    service.retry_model_turn(game.game_id)
    _wait(game, lambda: game.last_error is not None and game.status != "engine_thinking")
    assert game.status == "model_thinking"
