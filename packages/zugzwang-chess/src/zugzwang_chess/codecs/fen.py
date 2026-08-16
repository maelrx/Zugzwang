"""FEN codec: display and roundtrip."""

from __future__ import annotations

from zugzwang_core.domain.errors import OutputParseError

from ..environment.standard import START_FEN, ChessGameState


def fen_from_state(state: ChessGameState) -> str:
    return state.fen


def parse_fen(value: str, *, raise_on_invalid: bool = True) -> ChessGameState | None:
    """Parse a FEN string into a state. Parsing only; legality is separate."""
    import chess

    text = value.strip()
    try:
        board = chess.Board(text)
    except ValueError as exc:
        if raise_on_invalid:
            raise OutputParseError(f"invalid FEN {value!r}", technical_context=str(exc)) from exc
        return None
    return ChessGameState(fen=board.fen())


def is_starting_fen(state: ChessGameState) -> bool:
    return state.fen == START_FEN and not state.move_stack
