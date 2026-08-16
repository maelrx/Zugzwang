"""State-reconstruction scoring (design §14.6).

Metrics: exact match, piece-square accuracy, auxiliary-state accuracy.
These are pure functions over FEN strings — no engine, no network.
"""

from __future__ import annotations

import chess


def _board_map(fen: str) -> dict[str, str]:
    board = chess.Board(fen)
    mapping: dict[str, str] = {}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        mapping[chess.square_name(square)] = piece.symbol() if piece else "."
    return mapping


def score_reconstruction(canonical_fen: str, predicted_fen: str) -> dict[str, float]:
    """Compare a predicted FEN against the canonical position."""
    canonical = _board_map(canonical_fen)
    try:
        predicted = _board_map(predicted_fen)
    except ValueError:
        predicted = {}
    exact = 1.0 if canonical_fen.split(" ")[0] == predicted_fen.split(" ")[0] else 0.0
    squares = [square for square in canonical if square in predicted]
    matching = sum(1 for square in squares if canonical[square] == predicted[square])
    piece_accuracy = (matching / 64.0) if canonical else 0.0
    canonical_aux = canonical_fen.split(" ")[1:5]
    predicted_aux = predicted_fen.split(" ")[1:5]
    aux_matching = sum(1 for a, b in zip(canonical_aux, predicted_aux, strict=False) if a == b)
    auxiliary_accuracy = (aux_matching / 4.0) if canonical_aux else 0.0
    return {
        "exact_match": exact,
        "piece_square_accuracy": round(piece_accuracy, 6),
        "auxiliary_state_accuracy": round(auxiliary_accuracy, 6),
    }
