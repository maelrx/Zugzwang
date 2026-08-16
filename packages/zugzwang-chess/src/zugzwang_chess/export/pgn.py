"""Strict PGN mainline export (design §14.9).

Mainline only: no annotations, no variations, no NAGs. The initial position
is exported through a FEN tag when non-standard. Full chess rules history
(tags) stays minimal and honest.
"""

from __future__ import annotations

from typing import cast

from ..environment.standard import ChessGameState

_PGN_HEADERS = (
    ("Event", "Zugzwang"),
    ("Site", "local"),
    ("Result", "*"),
    ("White", "?"),
    ("Black", "?"),
    ("Variant", "Standard"),
)


def export_pgn_mainline(
    states: list[ChessGameState],
    *,
    white: str | None = None,
    black: str | None = None,
) -> str:
    """Export the mainline from a list of states (each a ply apart)."""

    if not states:
        raise ValueError("need at least one state to export PGN")
    initial = states[0]
    board = initial.to_board()
    san_moves: list[str] = []
    for state in states[1:]:
        if not state.move_stack:
            continue
        last = state.move_stack[-1]
        import chess

        move = chess.Move.from_uci(last)
        san_moves.append(board.san(move))
        board.push(move)
    headers: dict[str, str] = dict(_PGN_HEADERS)
    if white:
        headers["White"] = white
    if black:
        headers["Black"] = black
    final = states[-1]
    termination = final.termination
    result: str = cast(str, termination.result) if termination is not None else "*"
    if result == "white":
        result = "1-0"
    elif result == "black":
        result = "0-1"
    elif result == "draw":
        result = "1/2-1/2"
    headers["Result"] = result
    if initial.fen != "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
        headers["FEN"] = initial.fen
        headers["SetUp"] = "1"
    lines = [f'[{key} "{value}"]' for key, value in headers.items()]
    moves_rendered: list[str] = []
    for index in range(0, len(san_moves), 2):
        number = index // 2 + 1
        if index + 1 < len(san_moves):
            moves_rendered.append(f"{number}. {san_moves[index]} {san_moves[index + 1]}")
        else:
            moves_rendered.append(f"{number}. {san_moves[index]}")
    lines.append(" ".join(moves_rendered) + f" {result}")
    return "\n".join(lines) + "\n"
