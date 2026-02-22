from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import chess
import chess.pgn

from zugzwang.core.models import GameState


@dataclass
class ApplyMoveResult:
    ok: bool
    san: str
    error: str | None = None


class BoardManager:
    """Single wrapper around python-chess state and legality operations."""

    def __init__(self, initial_fen: str | None = None) -> None:
        self._board = chess.Board(initial_fen) if initial_fen else chess.Board()

    @property
    def board(self) -> chess.Board:
        return self._board

    def active_color(self) -> str:
        return "white" if self._board.turn == chess.WHITE else "black"

    def fen(self) -> str:
        return self._board.fen()

    def legal_moves_uci(self) -> list[str]:
        return [move.uci() for move in self._board.legal_moves]

    def legal_moves_san(self) -> list[str]:
        return [self._board.san(move) for move in self._board.legal_moves]

    def apply_move(self, move_uci: str) -> ApplyMoveResult:
        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            return ApplyMoveResult(ok=False, san="", error=f"invalid_uci:{move_uci}")

        if move not in self._board.legal_moves:
            return ApplyMoveResult(ok=False, san="", error=f"illegal_uci:{move_uci}")

        san = self._board.san(move)
        self._board.push(move)
        return ApplyMoveResult(ok=True, san=san)

    def is_terminal(self) -> bool:
        return self._board.is_game_over(claim_draw=True)

    def termination_reason(self) -> str | None:
        if self._board.is_checkmate():
            return "checkmate"
        if self._board.is_stalemate():
            return "stalemate"
        if self._board.is_seventyfive_moves() or self._board.can_claim_fifty_moves():
            return "draw_move_rule"
        if self._board.is_fivefold_repetition() or self._board.can_claim_threefold_repetition():
            return "draw_repetition"
        if self._board.is_insufficient_material():
            return "draw_insufficient_material"
        if self._board.is_game_over(claim_draw=True):
            return "draw_rule"
        return None

    def result(self) -> str:
        return self._board.result(claim_draw=True)

    def pgn(self) -> str:
        game = chess.pgn.Game.from_board(self._board)
        exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
        return game.accept(exporter).strip()

    def phase(self) -> str:
        piece_count = len(self._board.piece_map())
        if piece_count <= 10:
            return "endgame"
        if self._board.fullmove_number <= 12:
            return "opening"
        return "middlegame"

    def game_state(self, history_uci: Iterable[str]) -> GameState:
        history_list = list(history_uci)
        return GameState(
            fen=self.fen(),
            pgn=self.pgn(),
            move_number=self._board.fullmove_number,
            ply_number=len(self._board.move_stack),
            active_color=self.active_color(),
            legal_moves_uci=self.legal_moves_uci(),
            legal_moves_san=self.legal_moves_san(),
            phase=self.phase(),
            is_check=self._board.is_check(),
            is_terminal=self.is_terminal(),
            termination_reason=self.termination_reason(),
            history_uci=history_list,
        )
