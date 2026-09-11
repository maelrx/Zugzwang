"""Arena game: state machine, persistence and PGN export.

One game = human vs model, alternating plies, model turn driven by
:class:`ArenaDecisionLoop`. State survives restarts via ``game.json``; the
verbatim provider evidence lives beside it in ``calls.jsonl``; a PGN is
rewritten after every committed ply (derived artifact — raw evidence is
append-only and never rewritten).
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zugzwang_chess.replay import replay_positions

from .loop import DEFAULT_DIRECTIVE, DecisionOutcome
from .positions import BoardFacade


@dataclass(slots=True)
class MoveRecord:
    ply: int
    side: str
    actor: str  # human | model
    uci: str
    san: str
    latency_ms: int | None = None
    tokens_out: int | None = None
    rounds: int | None = None
    error: str | None = None


@dataclass
class ArenaGame:
    game_id: str
    created_at: str
    setup: dict[str, Any]
    board: BoardFacade
    moves: list[MoveRecord] = field(default_factory=list["MoveRecord"])
    status: str = "human_turn"  # human_turn | model_thinking | finished
    result: dict[str, Any] | None = None
    last_error: str | None = None
    model_note: dict[str, Any] | None = None
    model_progress: dict[str, Any] | None = None
    isolation_violation: bool = False
    assistance_violations: list[dict[str, Any]] = field(default_factory=list["dict[str, Any]"])
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    call_sink: Callable[[dict[str, Any]], None] | None = field(default=None, repr=False)

    # -- identity / naming --------------------------------------------------------

    @property
    def human_color(self) -> str:
        return str(self.setup.get("human_color", "white"))

    @property
    def model_color(self) -> str:
        return "black" if self.human_color == "white" else "white"

    def model_label(self) -> str:
        return f"{self.setup.get('model', 'model')} ({self.setup.get('provider', 'provider')})"

    # -- serialization -------------------------------------------------------------

    def to_state(self, *, include_dests: bool = True) -> dict[str, Any]:
        dests: dict[str, list[str]] | None = None
        promotable: list[str] | None = None
        if (
            include_dests
            and self.status == "human_turn"
            and self.board.turn == self.human_color
            and not self.board.terminal
        ):
            dests, promotable = self.board.dests()
        return {
            "id": self.game_id,
            "created_at": self.created_at,
            "setup": dict(self.setup),
            "status": self.status,
            "human_color": self.human_color,
            "model_color": self.model_color,
            "fen": self.board.board.fen(),
            "turn": self.board.turn,
            "check": self.board.board.is_check(),
            "last_uci": self.moves[-1].uci if self.moves else None,
            "moves": [asdict(record) for record in self.moves],
            "thinking": self.status == "model_thinking",
            "last_error": self.last_error,
            "model_progress": self.model_progress,
            "isolation_violation": self.isolation_violation,
            "assistance_violations": list(self.assistance_violations),
            "result": self.result,
            "dests": dests,
            "promotable": promotable,
            "directive_default": DEFAULT_DIRECTIVE,
            "positions": replay_positions(self.board.start_fen, self.board.moves),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.game_id,
            "created_at": self.created_at,
            "setup": dict(self.setup),
            "status": self.status,
            "human_color": self.human_color,
            "plies": len(self.board.moves),
            "last_uci": self.moves[-1].uci if self.moves else None,
            "result": self.result,
        }

    # -- play ---------------------------------------------------------------------

    def apply_human_move(self, uci: str) -> None:
        if self.status != "human_turn" or self.board.turn != self.human_color:
            raise ValueError(f"game is not awaiting a human move (status={self.status})")
        side = self.board.turn
        san = self.board.san(uci)
        self.board.apply(uci)
        self.moves.append(
            MoveRecord(ply=len(self.board.moves), side=side, actor="human", uci=uci, san=san)
        )
        self.last_error = None
        self._settle_or_continue(model_next=True)

    def _settle_or_continue(self, *, model_next: bool) -> None:
        if self.board.terminal:
            self._finish_from_board()
            return
        self.status = "model_thinking" if model_next else "human_turn"

    def _finish_from_board(self) -> None:
        termination = self.board.termination
        self.status = "finished"
        self.result = {
            "score": self.board.result_score,
            "kind": str(termination.kind) if termination else "resign",
            "winner": termination.result if termination else None,
        }

    def resign(self) -> None:
        if self.status == "finished":
            return
        winner = "black" if self.human_color == "white" else "white"
        self.status = "finished"
        self.result = {
            "score": "1-0" if winner == "white" else "0-1",
            "kind": "resign",
            "winner": winner,
        }

    def record_model_outcome(self, outcome: DecisionOutcome, *, model_color: str) -> bool:
        """Persist a finished model turn; returns True when a move was played."""
        if self.status == "finished":
            return False
        if self.board.turn != model_color:
            raise ValueError("Model result does not belong to this turn")
        if outcome.status == "COMMITTED" and outcome.uci:
            side = self.board.turn
            san = self.board.san(outcome.uci)
            latency = max((call.latency_ms for call in outcome.calls), default=0)
            tokens = next(
                (call.output_tokens for call in reversed(outcome.calls) if call.output_tokens), None
            )
            self.board.apply(outcome.uci)
            self.moves.append(
                MoveRecord(
                    ply=len(self.board.moves),
                    side=side,
                    actor="model",
                    uci=outcome.uci,
                    san=san,
                    latency_ms=latency,
                    tokens_out=tokens,
                    rounds=outcome.rounds_used,
                )
            )
            hypothesis = " ".join((outcome.final_text or "").split())
            self.model_note = {
                "fen": self.board.board.fen(),
                "my_move": san,
                "hypothesis": hypothesis[:600],
            }
            self.last_error = None
            self._settle_or_continue(model_next=False)
            return True
        self.last_error = f"{outcome.status}: {outcome.error or 'sem detalhes'}"
        if outcome.status == "PROVIDER_ISOLATION_VIOLATION":
            # Security failures are permanent game-level taint: never cleared by
            # a later clean turn, never retried, always kept in the game record.
            self.isolation_violation = True
            self.assistance_violations.append(
                {
                    "status": outcome.status,
                    "error": outcome.error or "provider isolation violation",
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
        # The human moved; the model failed to answer. Play returns to the
        # human — a failed provider turn is never a move.
        self.status = "human_turn"
        return False

    def turn_owner(self) -> str:
        return self.board.turn

    # -- persistence ----------------------------------------------------------------

    def dump(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "zugzwang.arena-game/v1",
            "id": self.game_id,
            "created_at": self.created_at,
            "setup": dict(self.setup),
            "status": self.status,
            "result": self.result,
            "last_error": self.last_error,
            "model_progress": self.model_progress,
            "model_note": self.model_note,
            "isolation_violation": self.isolation_violation,
            "assistance_violations": list(self.assistance_violations),
            "moves": [asdict(record) for record in self.moves],
            "start_fen": self.board.start_fen,
            "board_moves": list(self.board.moves),
        }
        target = directory / f"{self.game_id}.json"
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)
        self.write_pgn(directory)

    def pgn_text(self) -> str:
        import chess.pgn

        game = chess.pgn.Game()
        game.setup(chess.Board(self.board.start_fen))
        game.headers["Event"] = "Arena ZGW-0108 (non-canonical)"
        game.headers["Site"] = "local"
        game.headers["Date"] = self.created_at[:10].replace("-", ".")
        human = "Humano (Mael)"
        game.headers["White"] = human if self.human_color == "white" else self.model_label()
        game.headers["Black"] = human if self.human_color == "black" else self.model_label()
        game.headers["Result"] = self.result["score"] if self.result else "*"
        node = game
        board = chess.Board(self.board.start_fen)
        for record in self.moves:
            move = chess.Move.from_uci(record.uci)
            if move not in board.legal_moves:
                raise ValueError(f"PGN export hit an illegal move {record.uci!r}")
            node = node.add_main_variation(move)
            board.push(move)
        return str(game)

    def write_pgn(self, directory: Path) -> None:
        target = directory / f"{self.game_id}.pgn"
        tmp = target.with_suffix(".pgn.tmp")
        tmp.write_text(self.pgn_text(), encoding="utf-8")
        os.replace(tmp, target)


def new_game_id() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"arena-{stamp}-{random.randint(1000, 9999)}"


def load_game(path: Path, call_sink: Callable[[dict[str, Any]], None] | None = None) -> ArenaGame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    board = BoardFacade(
        start_fen=payload.get("start_fen") or None,
        moves=payload.get("board_moves") or [],
        ascii_enabled=bool(payload["setup"].get("ascii", False)),
        history_plies=int(payload["setup"].get("history_plies", 12)),
    )
    game = ArenaGame(
        game_id=payload["id"],
        created_at=payload["created_at"],
        setup=dict(payload["setup"]),
        board=board,
        status=str(payload.get("status", "human_turn")),
        result=payload.get("result"),
        last_error=payload.get("last_error"),
        model_note=payload.get("model_note"),
        model_progress=payload.get("model_progress"),
        isolation_violation=bool(payload.get("isolation_violation", False)),
        assistance_violations=list(payload.get("assistance_violations", [])),
        call_sink=call_sink,
    )
    game.moves = [MoveRecord(**record) for record in payload.get("moves", [])]
    # A game that was mid-model-turn when the service died returns to the
    # human: no ghost "thinking" state survives a restart.
    if game.status == "model_thinking":
        game.status = "human_turn"
        if game.model_progress:
            game.model_progress["status"] = "interrupted"
            game.model_progress["finished_at"] = time.time()
    return game


__all__ = ["ArenaGame", "MoveRecord", "load_game", "new_game_id"]
