"""Private arena replay projection; the recorded trajectory is never modified."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import chess


def replay_positions(start_fen: str, moves: Sequence[str]) -> list[dict[str, Any]]:
    board = chess.Board(start_fen)
    positions: list[dict[str, Any]] = []
    for ply in range(len(moves) + 1):
        san = None
        if ply:
            move = chess.Move.from_uci(moves[ply - 1])
            if move not in board.legal_moves:
                raise ValueError(f"Illegal recorded move at ply {ply}: {move.uci()}")
            san = board.san(move)
            board.push(move)
        positions.append(
            {
                "ply": ply,
                "fen": board.fen(),
                "last_uci": moves[ply - 1] if ply else None,
                "san": san,
                "check": board.is_check(),
                "turn": "white" if board.turn else "black",
                "fullmove": board.fullmove_number,
            }
        )
    return positions
