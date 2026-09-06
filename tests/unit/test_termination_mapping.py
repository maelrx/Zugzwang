"""Termination mapping v2 (ZGW-0087 D2 fix, executed in CB-WO-04).

The 75-move automatic draw is recorded as SEVENTYFIVE_MOVE; the historical
FIFTY_MOVE kind stays defined for claim semantics; the mapping version is
exposed; pre-v2 records are never rewritten.
"""

import chess
import pytest

from zugzwang_chess.environment.standard import (
    TERMINATION_MAPPING_VERSION,
    TerminationKind,
    termination_for,
)

pytestmark = pytest.mark.unit


def _rook_endgame_with_clock(clock: int) -> chess.Board:
    """KRvKR board (material sufficient for both sides, no pawn history)."""
    board = chess.Board()
    board.clear()
    board.set_piece_at(chess.E1, chess.Piece.from_symbol("K"))
    board.set_piece_at(chess.E8, chess.Piece.from_symbol("k"))
    board.set_piece_at(chess.A1, chess.Piece.from_symbol("R"))
    board.set_piece_at(chess.H8, chess.Piece.from_symbol("R"))
    board.halfmove_clock = clock
    return board


def test_seventyfive_moves_map_to_their_own_kind() -> None:
    """75 lances automaticamente empatados não usam mais a categoria FIFTY_MOVE."""
    termination = termination_for(_rook_endgame_with_clock(150))
    assert termination is not None
    assert termination.kind == TerminationKind.SEVENTYFIVE_MOVE.value
    assert termination.kind != TerminationKind.FIFTY_MOVE.value
    assert termination.result == "draw"


def test_no_premature_termination_before_the_rule_fires() -> None:
    termination = termination_for(_rook_endgame_with_clock(120))
    assert termination is None


def test_fifty_move_kind_is_preserved_for_claims() -> None:
    """The historical kind remains defined — claims are not automatic (§8.7)."""
    assert TerminationKind.FIFTY_MOVE.value == "fifty_move"
    assert TerminationKind.SEVENTYFIVE_MOVE.value == "seventyfive_move"


def test_mapping_version_is_exposed() -> None:
    """PRD §3.5[^R03]: the mapping version is exposed alongside the kinds."""
    assert TERMINATION_MAPPING_VERSION == "v2"
