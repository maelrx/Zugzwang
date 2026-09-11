"""ChessPerception: the deterministic L0 extractor (PRD §8, §38.4).

Builds PositionPackets from integral state using the rules substrate only.
It never calls an evaluator, never ranks, never prunes and never classifies
advantage (TEST-010). The same state with the same policy hash always yields
a byte-identical packet content hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import chess

from ..codecs.ascii_board import render_ascii
from ..environment.standard import ChessGameState, StandardChessEnvironment
from .packet import (
    CognitionError,
    LegalActionItem,
    PacketHistoryItem,
    PacketLegalActions,
    PacketProvenance,
    PacketRelations,
    PacketRepresentation,
    PacketState,
    PacketTerminal,
    PositionPacket,
)
from .relations import RELATIONS_SEMANTICS_VERSION, absolute_pins, checkers

PERCEPTION_VERSION = "chess-perception/v0.2"


@dataclass(frozen=True, slots=True)
class PacketExposure:
    """Declated L0 exposure policy for packet building (ZGW-0103 R3).

    Mirrors the manifest's ``protocol.observation`` for the cognitive path:
    ``position.ascii`` and ``history`` are delivered for real or the declared
    combination is rejected upstream — never silently ignored (dossier §5.1).
    """

    fen: bool = True
    ascii: bool = False
    history_mode: str = "none"  # none | last_n | full
    history_plies: int = 0
    history_notation: str = "uci"  # uci | san

    @classmethod
    def from_observation(cls, observation: dict[str, Any] | None) -> PacketExposure:
        policy: dict[str, Any] = dict(observation) if isinstance(observation, dict) else {}
        position_raw = policy.get("position")
        position = cast("dict[str, Any]", position_raw) if isinstance(position_raw, dict) else {}
        history_raw = policy.get("history")
        history = cast("dict[str, Any]", history_raw) if isinstance(history_raw, dict) else {}
        mode = str(history.get("mode", "none"))
        if mode not in {"none", "last_n", "full"}:
            raise CognitionError("INVALID_ARGUMENTS", f"unknown history mode {mode!r}")
        plies_raw = history.get("plies", 0)
        plies = int(plies_raw) if isinstance(plies_raw, int) and plies_raw > 0 else 0
        if mode == "last_n" and plies == 0:
            raise CognitionError(
                "INVALID_ARGUMENTS", "history mode last_n requires a positive plies value"
            )
        notation = str(history.get("notation", "uci"))
        if notation not in {"uci", "san"}:
            raise CognitionError("INVALID_ARGUMENTS", f"unknown history notation {notation!r}")
        return cls(
            fen=position.get("fen", True) is not False,
            ascii=position.get("ascii", False) is True,
            history_mode=mode,
            history_plies=plies,
            history_notation=notation,
        )


class ChessPerception:
    """Deterministic L0 perception over one chess environment."""

    def __init__(
        self,
        environment: StandardChessEnvironment,
        rules_version: str,
        policy_hash: str,
        page_size: int = 32,
        exposure: PacketExposure | None = None,
    ) -> None:
        self._environment = environment
        self._rules_version = rules_version
        self._policy_hash = policy_hash
        if page_size < 1:
            raise CognitionError("INVALID_ARGUMENTS", "page_size must be >= 1")
        self._page_size = page_size
        self._exposure = exposure or PacketExposure()

    def build_packet(
        self,
        state: ChessGameState,
        node_id: str,
        *,
        cursor: int = 0,
        include_representation: bool = True,
        requested_scope: str = "minimal",
    ) -> PositionPacket:
        """Build one authorized projection of the state (§8.2)."""
        board = state.to_board()
        legal_set = self._environment.legal_actions(state)

        state_key, _position_key = self._keys(state, board)
        actions = legal_set.actions
        start = max(0, cursor)
        page = actions[start : start + self._page_size]
        items: list[LegalActionItem] = []
        for offset, move in enumerate(page):
            chess_move = chess.Move.from_uci(move.uci)
            origin_piece = board.piece_at(chess_move.from_square)
            items.append(
                LegalActionItem.build(
                    index=start + offset,
                    uci=move.uci,
                    state_key=state_key,
                    action_schema_version="uci/v1",
                    policy_hash=self._policy_hash,
                    from_square=chess.square_name(chess_move.from_square),
                    to_square=chess.square_name(chess_move.to_square),
                    piece=origin_piece.symbol() if origin_piece else "?",
                    is_capture=board.is_capture(chess_move),
                    is_castling=board.is_castling(chess_move),
                    promotion=chess.piece_symbol(chess_move.promotion)
                    if chess_move.promotion
                    else None,
                )
            )
        next_cursor = start + self._page_size if start + self._page_size < len(actions) else None

        termination = state.termination
        terminal = PacketTerminal(
            automatic=termination is not None,
            kind=termination.kind if termination else None,
            result=termination.result if termination else None,
            claim_policy=None,  # claims never become automatic termination (§8.7)
        )

        relations = self._relations(board, requested_scope)
        representation = self._representation(state, board, include_representation)
        history = self._history(state)

        packet = PositionPacket(
            state=PacketState(
                state_key=state_key,
                node_id=node_id,
                variant=state.variant,
                side_to_move=state.side_to_move,
                history_completeness="full" if state.move_stack else "from_anchor",
            ),
            representation=representation,
            legal_actions=PacketLegalActions(
                total_count=len(actions),
                set_hash=legal_set.legal_hash,
                ordering=legal_set.ordering_policy,
                items=tuple(items),
                next_cursor=next_cursor,
                # A page with no next cursor IS the terminal page of the
                # legal set — even when reached via cursor pagination
                # (arena full games 2026-09-07: "complete": false on the
                # last page read as "more moves exist" and multiplied
                # redundant observe calls).
                complete=next_cursor is None,
            ),
            relations=PacketRelations(
                semantics_version=RELATIONS_SEMANTICS_VERSION,
                requested_scope=requested_scope,
                items=relations,
                complete=True,
            ),
            terminal=terminal,
            provenance=PacketProvenance(
                rules_version=self._rules_version,
                perception_version=PERCEPTION_VERSION,
                policy_hash=self._policy_hash,
            ),
            history=history,
        )
        return packet

    def identity_keys(self, state: ChessGameState) -> tuple[str, str]:
        """(state_key, position_key) of one state (§7.2) — the same derivation
        the packet uses, exposed for action-id validation over the complete
        legal set (not only the first packet page)."""
        return self._keys(state, state.to_board())

    def _keys(self, state: ChessGameState, board: chess.Board) -> tuple[str, str]:
        parts = state.fen.split(" ")
        placement = parts[0]
        side = parts[1] if len(parts) > 1 else "w"
        castling = parts[2] if len(parts) > 2 else "-"
        ep = parts[3] if len(parts) > 3 else "-"
        ep_legal = ep if (ep != "-" and _is_legal_ep(board, ep)) else "-"
        from zugzwang_core.domain.cognition import position_key_v2, state_key_v2

        return (
            state_key_v2(state.fingerprint(), state.variant, "standard-rules/v1"),
            position_key_v2(placement, side, castling, ep_legal),
        )

    def _representation(
        self, state: ChessGameState, board: chess.Board, include: bool
    ) -> PacketRepresentation:
        if not include:
            return PacketRepresentation()
        piece_map = {
            chess.square_name(sq): piece.symbol() for sq, piece in board.piece_map().items()
        }
        return PacketRepresentation(
            fen=state.fen if self._exposure.fen else None,
            piece_map=piece_map,
            ascii=render_ascii(state) if self._exposure.ascii else None,
        )

    def _history(self, state: ChessGameState) -> tuple[PacketHistoryItem, ...]:
        """Formal trajectory window per the declared exposure (ZGW-0103 R3).

        uci strings come straight from the committed move stack; san is derived
        from the replaying board — formal notation, never commentary.
        """
        mode = self._exposure.history_mode
        if mode == "none" or not state.move_stack:
            return ()
        stack = list(state.move_stack)
        if mode == "last_n":
            stack = stack[-self._exposure.history_plies :]
        base_index = len(state.move_stack) - len(stack)
        items: list[PacketHistoryItem] = []
        replay = chess.Board()
        if state.initial_fen and state.initial_fen != chess.STARTING_FEN:
            replay = chess.Board(state.initial_fen)
        # Reconstruct the omitted prefix before encoding the visible window.
        # Replaying only the suffix from the initial board corrupts its context.
        for uci in state.move_stack[:base_index]:
            replay.push(chess.Move.from_uci(uci))
        for offset, uci in enumerate(stack):
            move = chess.Move.from_uci(uci)
            san = replay.san(move) if self._exposure.history_notation == "san" else None
            replay.push(move)
            items.append(PacketHistoryItem(ply_index=base_index + offset, uci=uci, san=san))
        return tuple(items)

    def _relations(self, board: chess.Board, requested_scope: str) -> tuple[dict[str, Any], ...]:
        if requested_scope != "minimal":
            raise CognitionError(
                "INVALID_ARGUMENTS",
                f"unknown relations scope {requested_scope!r}; expected 'minimal'",
            )
        return (*checkers(board), *absolute_pins(board))


def _is_legal_ep(board: chess.Board, ep_square: str) -> bool:
    """A fen ep square counts in the position key only when a legal en-passant
    capture actually exists (normalized opportunity, PRD §7.4)."""
    target = chess.parse_square(ep_square)
    return any(m.to_square == target and board.is_en_passant(m) for m in board.legal_moves)


def perception_version() -> str:
    return PERCEPTION_VERSION
