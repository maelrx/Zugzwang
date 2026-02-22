from __future__ import annotations

from zugzwang.core.board import BoardManager


def test_illegal_move_is_rejected() -> None:
    board = BoardManager()
    result = board.apply_move("e2e5")
    assert not result.ok
    assert result.error is not None
    assert board.fen().startswith("rnbqkbnr")


def test_legal_move_is_applied() -> None:
    board = BoardManager()
    result = board.apply_move("e2e4")
    assert result.ok
    assert result.san == "e4"
    assert board.active_color() == "black"
