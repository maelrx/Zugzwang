from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import chess
import chess.engine

MATE_SCORE_CP = 100_000


@dataclass
class StockfishEval:
    best_move_uci: str
    centipawn_loss: int
    eval_before_cp: int | None
    eval_after_cp: int | None


class StockfishEvaluator:
    """Stockfish adapter for deterministic move-quality evaluation."""

    def __init__(
        self,
        depth: int = 12,
        path: str | None = None,
        threads: int = 1,
        hash_mb: int = 128,
    ) -> None:
        self.depth = depth
        self.path = path or os.environ.get("STOCKFISH_PATH") or "stockfish"
        self.threads = threads
        self.hash_mb = hash_mb
        self._engine: chess.engine.SimpleEngine | None = None

    def _ensure_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is not None:
            return self._engine
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Stockfish binary not found. Set STOCKFISH_PATH in .env or evaluation.stockfish.path in config."
            ) from exc

        try:
            self._engine.configure({"Threads": self.threads, "Hash": self.hash_mb})
        except chess.engine.EngineError:
            # Some binaries may reject one or both options; continue with defaults.
            pass
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def __enter__(self) -> "StockfishEvaluator":
        self._ensure_engine()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _analyse(self, board: chess.Board) -> dict[str, Any]:
        engine = self._ensure_engine()
        info = engine.analyse(board, chess.engine.Limit(depth=self.depth))
        return info

    @staticmethod
    def _score_cp(info: dict[str, Any], pov_color: chess.Color) -> int:
        score = info["score"].pov(pov_color)
        cp = score.score(mate_score=MATE_SCORE_CP)
        if cp is None:
            return 0
        return int(cp)

    def evaluate_position(self, fen: str) -> tuple[str | None, int]:
        board = chess.Board(fen)
        info = self._analyse(board)
        pv = info.get("pv", [])
        best_move = pv[0].uci() if pv else None
        eval_cp = self._score_cp(info, board.turn)
        return best_move, eval_cp

    def evaluate_move(self, fen: str, move_uci: str) -> StockfishEval:
        board_before = chess.Board(fen)
        mover = board_before.turn
        move = chess.Move.from_uci(move_uci)
        if move not in board_before.legal_moves:
            raise ValueError(f"Illegal move '{move_uci}' for FEN '{fen}'")

        info_before = self._analyse(board_before)
        pv = info_before.get("pv", [])
        best_move = pv[0].uci() if pv else move_uci
        eval_before_for_mover = self._score_cp(info_before, mover)

        board_after = chess.Board(fen)
        board_after.push(move)
        info_after = self._analyse(board_after)
        # After the move, engine score is from side-to-move (opponent), so invert for mover.
        eval_after_for_mover = -self._score_cp(info_after, board_after.turn)
        cp_loss = max(0, eval_before_for_mover - eval_after_for_mover)

        return StockfishEval(
            best_move_uci=best_move,
            centipawn_loss=int(cp_loss),
            eval_before_cp=int(eval_before_for_mover),
            eval_after_cp=int(eval_after_for_mover),
        )
