"""L0-R minimal formal relations (PRD §8.4).

Formal facts only: checkers, absolute pins (piece-king-pinner ray), geometric
attacks as published by the rules substrate, and legal captures restricted to
the side to move. Relative pins, "hanging", "fork" and similar strategic terms
are NOT facts and never appear here. A pinned piece may still appear in the
substrate's attack maps — that is documented substrate behaviour, not a bug.
"""

from __future__ import annotations

from typing import Any

import chess

RELATIONS_SEMANTICS_VERSION = "l0r-minimal/v1"


def checkers(board: chess.Board) -> tuple[dict[str, Any], ...]:
    """Attackers giving check to the side to move (§8.4 'checkers')."""
    return tuple({"square": chess.square_name(sq)} for sq in board.checkers())


def _ray_beyond(king_square: int, pinned_square: int) -> list[int]:
    """Squares on the king→pinned line, beyond the pinned piece."""
    kf, kr = chess.square_file(king_square), chess.square_rank(king_square)
    pf, pr = chess.square_file(pinned_square), chess.square_rank(pinned_square)
    df, dr = pf - kf, pr - kr
    if df == 0 and dr == 0:
        return []
    if not (df == 0 or dr == 0 or abs(df) == abs(dr)):
        return []
    step_f = (df > 0) - (df < 0)
    step_r = (dr > 0) - (dr < 0)
    squares: list[int] = []
    f, r = pf + step_f, pr + step_r
    while 0 <= f < 8 and 0 <= r < 8:
        squares.append(chess.square(f, r))
        f += step_f
        r += step_r
    return squares


def absolute_pins(board: chess.Board) -> tuple[dict[str, Any], ...]:
    """Absolute pins against the side-to-move's king (§8.4 'absolute_pin').

    A piece is absolutely pinned when removing it exposes its own king to the
    pinner along the piece-king ray. Relative pins are out of L0-R minimal.
    """
    king_square = board.king(board.turn)
    if king_square is None:
        return ()
    pins: list[dict[str, Any]] = []
    for square, piece in board.piece_map().items():
        if piece.color != board.turn or not board.is_pinned(board.turn, square):
            continue
        pinner_square = next(
            (
                sq
                for sq in _ray_beyond(king_square, square)
                if (p := board.piece_at(sq)) is not None and p.color != board.turn
            ),
            None,
        )
        if pinner_square is None:
            continue
        pins.append(
            {
                "kind": "absolute_pin",
                "piece": piece.symbol(),
                "piece_square": chess.square_name(square),
                "king_square": chess.square_name(king_square),
                "pinner_square": chess.square_name(pinner_square),
                "ray": f"{chess.square_name(pinner_square)}-{chess.square_name(king_square)}",
            }
        )
    return tuple(pins)


def geometric_attacks(board: chess.Board, square: str) -> tuple[str, ...]:
    """Substrate attack map of one square (§8.4 'geometric_attack').

    Follows the public semantics of the rules substrate: it does not guarantee
    a legal move and is not safety of the target square.
    """
    return tuple(sorted(chess.square_name(s) for s in board.attacks(chess.parse_square(square))))


def legal_captures(board: chess.Board, uci: str) -> bool:
    """True only when the action is a legal capture for the side to move
    (§8.4 'legal_capture') — never evaluated for the opponent's turn."""
    move = chess.Move.from_uci(uci)
    return move in board.legal_moves and board.is_capture(move)
