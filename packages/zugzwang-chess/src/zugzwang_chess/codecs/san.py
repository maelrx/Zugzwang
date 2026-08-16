"""SAN codec: interface notation only (design §14.3).

SAN is contextual and may carry ``+``/``#`` markers; those must be recorded
because they leak mate/check information to the model (leakage annotations).
"""

from __future__ import annotations

from dataclasses import dataclass

from zugzwang_core.domain.errors import OutputParseError

from ..environment.standard import ChessGameState, ChessMove


@dataclass(frozen=True, slots=True)
class SanMove:
    """A parsed SAN move plus its leakage-relevant markers."""

    san: str
    uci: str
    has_check_marker: bool = False
    has_mate_marker: bool = False


def parse_san(
    value: str, state: ChessGameState, *, raise_on_invalid: bool = True
) -> SanMove | None:
    """Parse SAN against a concrete state (SAN is state-dependent)."""
    text = value.strip()
    board = state.to_board()
    try:
        move = board.parse_san(text)
    except ValueError as exc:
        if raise_on_invalid:
            raise OutputParseError(
                f"invalid SAN move {value!r} for this position",
                technical_context=f"fen={state.fen}",
            ) from exc
        return None
    return SanMove(
        san=board.san(move),
        uci=move.uci(),
        has_check_marker=text.endswith("+"),
        has_mate_marker=text.endswith("#"),
    )


def format_san(state: ChessGameState, move: ChessMove) -> str:
    board = state.to_board()
    return board.san(__import__("chess").Move.from_uci(move.uci))


def san_line(state: ChessGameState, uci_moves: list[str] | tuple[str, ...]) -> str:
    """Render a SAN line for a move sequence starting from the state."""
    board = state.to_board()
    result: list[str] = []
    for uci in list(uci_moves):
        move = __import__("chess").Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        result.append(board.san(move))
        board.push(move)
    return " ".join(result)
