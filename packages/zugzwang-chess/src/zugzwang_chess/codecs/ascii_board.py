"""ASCII board renderer for text observations."""

from __future__ import annotations

from ..environment.standard import ChessGameState


def render_ascii(state: ChessGameState) -> str:
    board = state.to_board()
    return board.unicode(invert_color=False, borders=True)
