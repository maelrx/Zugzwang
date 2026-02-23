from __future__ import annotations

import random

import chess
import chess.engine

from zugzwang.core.board import BoardManager
from zugzwang.core.players import EnginePlayer


class _StubEngine:
    def __init__(self) -> None:
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, options):  # type: ignore[no-untyped-def]
        self.configure_calls.append(options)
        return None

    def play(self, board: chess.Board, limit):  # type: ignore[no-untyped-def]
        move = next(iter(board.legal_moves))
        return type("Result", (), {"move": move})()

    def quit(self) -> None:
        return None


def test_engine_player_chooses_legal_move(monkeypatch) -> None:
    monkeypatch.setattr(
        "zugzwang.core.players.chess.engine.SimpleEngine.popen_uci",
        lambda _: _StubEngine(),
    )
    board = BoardManager()
    state = board.game_state([])

    player = EnginePlayer(name="stockfish", path="stub-engine", rng=random.Random(3))
    decision = player.choose_move(state)
    player.close()

    assert decision.parse_ok is True
    assert decision.is_legal is True
    assert decision.move_uci in state.legal_moves_uci
    assert decision.provider_calls == 1
    assert decision.provider_model.startswith("engine:")


def test_engine_player_falls_back_when_engine_missing(monkeypatch) -> None:
    def _raise_missing(_):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("not found")

    monkeypatch.setattr(
        "zugzwang.core.players.chess.engine.SimpleEngine.popen_uci",
        _raise_missing,
    )
    board = BoardManager()
    state = board.game_state([])

    player = EnginePlayer(name="stockfish", path="missing-engine", rng=random.Random(3))
    decision = player.choose_move(state)

    assert decision.parse_ok is False
    assert decision.move_uci in state.legal_moves_uci
    assert decision.provider_calls == 0
    assert decision.error == "provider_engine_unavailable"


def test_engine_player_configures_native_uci_elo(monkeypatch) -> None:
    stub_engine = _StubEngine()
    monkeypatch.setattr(
        "zugzwang.core.players.chess.engine.SimpleEngine.popen_uci",
        lambda _: stub_engine,
    )
    board = BoardManager()
    state = board.game_state([])

    player = EnginePlayer(
        name="stockfish",
        path="stub-engine",
        rng=random.Random(11),
        uci_limit_strength=True,
        uci_elo=1200,
    )
    _ = player.choose_move(state)
    player.close()

    assert {"UCI_LimitStrength": True} in stub_engine.configure_calls
    assert {"UCI_Elo": 1200} in stub_engine.configure_calls
