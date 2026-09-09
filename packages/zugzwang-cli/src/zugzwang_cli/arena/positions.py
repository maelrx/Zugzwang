"""Arena board substrate: the REAL rules kernel and L0 perception.

No run machinery (journal, budgets, CAS) — those belong to canonical runs.
Everything the model sees (packets, action ids, terminal facts) comes from the
same ``ChessPerception`` and ``StandardChessRulesKernel`` the campaigns use,
so arena games behave like fullgame experiments on the wire.
"""

from __future__ import annotations

import hashlib

import chess

from zugzwang_chess.cognition.packet import PositionPacket, require_action_belongs
from zugzwang_chess.cognition.perception import ChessPerception, PacketExposure
from zugzwang_chess.environment.standard import (
    ChessGameState,
    ChessMove,
    StandardChessEnvironment,
    StandardChessRulesKernel,
)
from zugzwang_core.domain.cognition import action_id_v2

ARENA_RULES_VERSION = "standard-rules/v1"
ARENA_POLICY_HASH = hashlib.sha256(b"zugzwang-arena/v1").hexdigest()
ACTION_SCHEMA_VERSION = "uci/v1"

RESULT_SCORE = {"white": "1-0", "black": "0-1", "draw": "1/2-1/2"}


class BoardFacade:
    """Position, legality and packets for one arena game (single source)."""

    def __init__(
        self,
        *,
        start_fen: str | None = None,
        moves: tuple[str, ...] | list[str] = (),
        ascii_enabled: bool = False,
        history_plies: int = 12,
    ) -> None:
        base = start_fen or chess.STARTING_FEN
        self._environment = StandardChessEnvironment()
        self._perception = ChessPerception(
            self._environment,
            rules_version=ARENA_RULES_VERSION,
            policy_hash=ARENA_POLICY_HASH,
            exposure=PacketExposure(
                fen=True,
                ascii=ascii_enabled,
                history_mode="last_n" if history_plies > 0 else "none",
                history_plies=max(0, history_plies),
                history_notation="uci",
            ),
        )
        self._kernel = StandardChessRulesKernel(self._environment)
        self.start_fen = base
        self.moves: list[str] = list(moves)

    @property
    def state(self) -> ChessGameState:
        return self._environment.state_from_moves(self.moves, start_fen=self.start_fen)

    @property
    def board(self) -> chess.Board:
        return self.state.to_board()

    @property
    def turn(self) -> str:
        return "white" if self.board.turn is chess.WHITE else "black"

    @property
    def termination(self):  # type: ignore[no-untyped-def]
        return self.state.termination

    @property
    def terminal(self) -> bool:
        return self.state.termination is not None

    @property
    def result_score(self) -> str:
        termination = self.state.termination
        if termination is None:
            return "*"
        return RESULT_SCORE.get(str(termination.result), "*")

    def legal_entries(self, state: ChessGameState) -> list[tuple[str, str]]:
        """(uci, action_id) over the COMPLETE legal set, kernel order."""
        state_key, _ = self._perception.identity_keys(state)
        return [
            (move.uci, action_id_for(state_key, move.uci))
            for move in self._kernel.legal_actions(state).actions
        ]

    def packet(self, state: ChessGameState, node_id: str, *, cursor: int = 0) -> PositionPacket:
        return self._perception.build_packet(state, node_id, cursor=cursor)

    def resolve_action(self, state: ChessGameState, action_ref: str) -> str | None:
        """Action id first, plain UCI as fallback (same order as the broker)."""
        entries = self.legal_entries(state)
        for uci, action_id in entries:
            if action_ref == action_id:
                return uci
        for uci, _ in entries:
            if action_ref == uci:
                return uci
        return None

    def apply(self, uci: str) -> ChessGameState:
        result = self._kernel.is_legal(self.state, ChessMove(uci=uci))
        if not result.legal:
            raise ValueError(f"illegal move {uci!r}: {result.reason}")
        self.moves.append(uci)
        return self.state

    def san(self, uci: str) -> str:
        board = self.board
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f"illegal move {uci!r}")
        return board.san(move)

    def dests(self) -> tuple[dict[str, list[str]], list[str]]:
        """Chessground dests for the side to move + target squares that promote."""
        board = self.board
        dests: dict[str, list[str]] = {}
        promotable: list[str] = []
        for move in board.legal_moves:
            origin = chess.square_name(move.from_square)
            target = chess.square_name(move.to_square)
            dests.setdefault(origin, []).append(target)
            if move.promotion and target not in promotable:
                promotable.append(target)
        return dests, promotable


def action_id_for(state_key: str, uci: str) -> str:
    return action_id_v2(state_key, uci, ACTION_SCHEMA_VERSION, ARENA_POLICY_HASH)


__all__ = [
    "ARENA_POLICY_HASH",
    "ARENA_RULES_VERSION",
    "BoardFacade",
    "action_id_for",
    "require_action_belongs",
]
