from __future__ import annotations

from typing import Any

import chess
import chess.svg

from zugzwang.ui.types import BoardStateFrame, GameRecordView, PlyMetrics


class ReplayService:
    def build_board_states(self, game_record: GameRecordView | dict[str, Any]) -> list[BoardStateFrame]:
        moves = _extract_moves(game_record)
        if not moves:
            board = chess.Board()
            return [
                BoardStateFrame(
                    ply_number=0,
                    fen=board.fen(),
                    svg=chess.svg.board(board=board, size=420),
                    move_uci=None,
                    move_san=None,
                    color=None,
                    raw_response=None,
                )
            ]

        first_fen = str(moves[0].get("fen_before") or chess.STARTING_FEN)
        start_board = chess.Board(first_fen)
        frames: list[BoardStateFrame] = [
            BoardStateFrame(
                ply_number=0,
                fen=start_board.fen(),
                svg=chess.svg.board(board=start_board, size=420),
                move_uci=None,
                move_san=None,
                color=None,
                raw_response=None,
            )
        ]

        for move in moves:
            ply_number = int(move.get("ply_number", len(frames)))
            color = _as_string(move.get("color"))
            fen_before = str(move.get("fen_before") or frames[-1].fen)
            decision = move.get("move_decision") if isinstance(move.get("move_decision"), dict) else {}
            move_uci = _as_string(decision.get("move_uci"))
            move_san = _as_string(decision.get("move_san"))
            raw_response = _as_string(decision.get("raw_response"))

            board = chess.Board(fen_before)
            parsed_move: chess.Move | None = None
            if move_uci:
                try:
                    parsed_move = chess.Move.from_uci(move_uci)
                except ValueError:
                    parsed_move = None

            if parsed_move and parsed_move in board.legal_moves:
                board.push(parsed_move)
            else:
                parsed_move = None

            frames.append(
                BoardStateFrame(
                    ply_number=ply_number,
                    fen=board.fen(),
                    svg=chess.svg.board(board=board, lastmove=parsed_move, size=420),
                    move_uci=move_uci,
                    move_san=move_san,
                    color=color,
                    raw_response=raw_response,
                )
            )

        return frames

    def frame_metrics(self, game_record: GameRecordView | dict[str, Any], ply: int) -> PlyMetrics:
        if ply <= 0:
            return _empty_metrics()

        moves = _extract_moves(game_record)
        payload: dict[str, Any] | None = None
        for move in moves:
            if int(move.get("ply_number", -1)) == ply:
                payload = move
                break

        if payload is None:
            return _empty_metrics()

        decision = payload.get("move_decision") if isinstance(payload.get("move_decision"), dict) else {}
        return PlyMetrics(
            tokens_input=int(decision.get("tokens_input", 0)),
            tokens_output=int(decision.get("tokens_output", 0)),
            latency_ms=int(decision.get("latency_ms", 0)),
            retry_count=int(decision.get("retry_count", 0)),
            parse_ok=bool(decision.get("parse_ok", False)),
            is_legal=bool(decision.get("is_legal", False)),
            cost_usd=float(decision.get("cost_usd", 0.0)),
            provider_model=str(decision.get("provider_model", "")),
            feedback_level=str(decision.get("feedback_level", "rich")),
            error=_as_string(decision.get("error")),
        )


def _extract_moves(game_record: GameRecordView | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(game_record, GameRecordView):
        return [move for move in game_record.moves if isinstance(move, dict)]

    moves = game_record.get("moves", []) if isinstance(game_record, dict) else []
    if not isinstance(moves, list):
        return []
    return [move for move in moves if isinstance(move, dict)]


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _empty_metrics() -> PlyMetrics:
    return PlyMetrics(
        tokens_input=0,
        tokens_output=0,
        latency_ms=0,
        retry_count=0,
        parse_ok=False,
        is_legal=False,
        cost_usd=0.0,
        provider_model="",
        feedback_level="rich",
        error=None,
    )
