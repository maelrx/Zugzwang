"""Standard chess environment behind the core Environment port (ADR-023).

``python-chess`` types never escape this package: the public contract exposes
``ChessGameState`` (frozen dataclass), ``ChessMove`` (UCI wrapper) and the
environment itself. The board object is private.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import chess

from zugzwang_core.domain.artifacts import ArtifactPayload
from zugzwang_core.domain.canonical import hash_canonical
from zugzwang_core.domain.errors import EnvironmentError_, IllegalActionError
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.environment import (
    EnvironmentDescriptor,
    EpisodeSpec,
    LegalActionSet,
    ObservationPolicy,
    Termination,
    Transition,
)

if TYPE_CHECKING:
    from chess import Board


STATE_MEDIA_TYPE = "application/x-zugzwang-chess-state+json"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class TerminationKind(StrEnum):
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    FIFTY_MOVE = "fifty_move"
    FIVEFOLD_REPETITION = "fivefold_repetition"
    MAX_PLIES = "max_plies"


@dataclass(frozen=True, slots=True)
class ChessMove:
    """Canonical action: a UCI string validated at parse time."""

    uci: str

    def __str__(self) -> str:
        return self.uci


@dataclass(frozen=True, slots=True)
class ChessGameState:
    """Integral state: position plus history for repetition (design §14.2).

    ``initial_fen`` anchors the position zero; ``fen`` is the current
    position; ``move_stack`` is the full action sequence since the initial
    position. Repetition detection replays from ``initial_fen``, so FEN-only
    snapshots can never falsify threefold claims.
    """

    fen: str = START_FEN
    initial_fen: str = START_FEN
    move_stack: tuple[str, ...] = ()
    variant: str = "standard"
    synthetic_clock: dict[str, JsonValue] = field(default_factory=lambda: {})

    def to_board(self) -> Board:
        board = chess.Board(self.initial_fen)
        for uci in self.move_stack:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise EnvironmentError_(
                    f"state history contains illegal move {uci!r}",
                    technical_context=f"initial_fen={self.initial_fen}",
                )
            board.push(move)
        return board

    @property
    def side_to_move(self) -> str:
        return "white" if self.fen.split(" ")[1] == "w" else "black"

    @property
    def fullmove_number(self) -> int:
        parts = self.fen.split(" ")
        return int(parts[5]) if len(parts) > 5 else 1

    @property
    def halfmove_clock(self) -> int:
        parts = self.fen.split(" ")
        return int(parts[4]) if len(parts) > 4 else 0

    @property
    def termination(self) -> Termination | None:
        board = self.to_board()
        return termination_for(board, reason="")

    @property
    def terminal(self) -> bool:
        return self.termination is not None

    @property
    def result(self) -> str | None:
        termination = self.termination
        if termination is None:
            return None
        return termination.result

    def fingerprint(self) -> str:
        """Canonical state fingerprint: FEN + initial FEN + move stack hash."""
        return hash_canonical(
            {"fen": self.fen, "initial_fen": self.initial_fen, "moves": list(self.move_stack)}
        )


def termination_for(board: Board, reason: str = "") -> Termination | None:
    """Formally verified termination (FR-027)."""
    if board.is_checkmate():
        winner = "black" if board.turn == chess.WHITE else "white"
        return Termination(kind=TerminationKind.CHECKMATE.value, result=winner, reason=reason)
    if board.is_stalemate():
        return Termination(kind=TerminationKind.STALEMATE.value, result="draw", reason=reason)
    if board.is_insufficient_material():
        return Termination(
            kind=TerminationKind.INSUFFICIENT_MATERIAL.value, result="draw", reason=reason
        )
    if board.is_fivefold_repetition():
        return Termination(
            kind=TerminationKind.FIVEFOLD_REPETITION.value, result="draw", reason=reason
        )
    if board.is_seventyfive_moves():
        return Termination(kind=TerminationKind.FIFTY_MOVE.value, result="draw", reason=reason)
    return None


def _push_state(state: ChessGameState, uci: str) -> ChessGameState:
    board = state.to_board()
    move = chess.Move.from_uci(uci)
    board.push(move)
    return ChessGameState(
        fen=board.fen(),
        initial_fen=state.initial_fen,
        move_stack=(*state.move_stack, uci),
        variant=state.variant,
        synthetic_clock=state.synthetic_clock,
    )


class StandardChessEnvironment:
    """Standard chess (variant=standard) behind the Environment port."""

    environment_id = "chess.standard"
    environment_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self) -> None:
        self._config: dict[str, JsonValue] = {}

    @property
    def descriptor(self) -> EnvironmentDescriptor:
        return EnvironmentDescriptor(
            environment_id=self.environment_id,
            environment_version=self.environment_version,
            plugin_api=self.plugin_api,
            state_type="chess.standard",
            action_type="uci",
            supports_snapshot=True,
        )

    def initial_state(self, episode: EpisodeSpec) -> ChessGameState:
        config = episode.config
        self._config = config
        fen = str(config.get("start_fen", START_FEN))
        return ChessGameState(fen=fen, initial_fen=fen)

    def state_from_moves(self, moves: list[str], start_fen: str | None = None) -> ChessGameState:
        base = start_fen or START_FEN
        state = ChessGameState(fen=base, initial_fen=base)
        for uci in moves:
            state = _push_state(state, uci)
        return state

    def observe(self, state: ChessGameState, policy: ObservationPolicy) -> dict[str, JsonValue]:
        from ..codecs.ascii_board import render_ascii
        from ..codecs.fen import fen_from_state
        from ..codecs.san import san_line

        settings = policy.settings
        observation: dict[str, JsonValue] = {}
        position = settings.get("position", {})
        if isinstance(position, dict):
            if position.get("fen", False):
                observation["fen"] = fen_from_state(state)
            if position.get("ascii", False):
                observation["ascii"] = render_ascii(state)
        else:
            observation["fen"] = fen_from_state(state)
        if settings.get("side_to_move", False):
            observation["side_to_move"] = state.side_to_move
        if settings.get("move_number", False):
            observation["move_number"] = state.fullmove_number
        history = settings.get("history", {})
        if isinstance(history, dict):
            mode = history.get("mode", "none")
            plies_raw = history.get("plies", 0)
            plies = int(plies_raw) if isinstance(plies_raw, (int, float)) else 0
            notation = history.get("notation", "uci")
            if mode == "last_n":
                moves = list(state.move_stack[-plies:])
                if notation == "san":
                    observation["history"] = san_line(state, moves)
                else:
                    observation["history"] = list(moves)
            elif mode == "full":
                observation["history"] = (
                    san_line(state, list(state.move_stack))
                    if notation == "san"
                    else list(state.move_stack)
                )
        legal_settings = settings.get("legal_actions", {})
        if isinstance(legal_settings, dict) and legal_settings.get("exposure") in {
            "always",
            "delayed",
        }:
            encoding = str(legal_settings.get("encoding", "uci"))
            legal_set = self.legal_actions(state, encoding=encoding)
            if encoding == "opaque_index":
                observation["legal_actions"] = list(range(len(legal_set.actions)))
                observation["legal_actions_hash"] = legal_set.legal_hash
            else:
                observation["legal_actions"] = [str(a) for a in legal_set.actions]
        return observation

    def legal_actions(
        self, state: ChessGameState, *, encoding: str = "canonical"
    ) -> LegalActionSet[ChessMove]:
        board = state.to_board()
        moves = [ChessMove(m.uci()) for m in board.legal_moves]
        actions = tuple(moves)
        ordering_policy = "python-chess-natural"
        ordering_version = chess.__version__
        legal_hash = hash_canonical(
            {
                "actions": [m.uci for m in moves],
                "state_fingerprint": state.fingerprint(),
                "ordering_policy": ordering_policy,
            }
        )
        leakage = (
            ("uci_notation_leaks_geometry",)
            if encoding == "uci"
            else ("opaque_indices_require_frozen_ordering",)
        )
        return LegalActionSet(
            actions=actions,
            ordering_policy=ordering_policy,
            ordering_version=ordering_version,
            encoding=encoding if encoding in {"uci", "opaque_index"} else "uci",
            legal_hash=legal_hash,
            leakage_annotations=leakage,
            source="rules_engine",
            state_fingerprint=state.fingerprint(),
        )

    def transition(
        self, state: ChessGameState, action: ChessMove
    ) -> Transition[ChessGameState, ChessMove]:
        board = state.to_board()
        try:
            move = chess.Move.from_uci(action.uci)
        except ValueError as exc:
            raise IllegalActionError(
                f"malformed move {action.uci!r}",
                technical_context="action must be canonical UCI",
            ) from exc
        if move not in board.legal_moves:
            raise IllegalActionError(
                f"move {action.uci!r} is not legal in this position",
                technical_context=f"fen={state.fen}",
            )
        board.push(move)
        termination = termination_for(board)
        next_state = ChessGameState(
            fen=board.fen(),
            initial_fen=state.initial_fen,
            move_stack=(*state.move_stack, action.uci),
            variant=state.variant,
            synthetic_clock=state.synthetic_clock,
        )
        if termination is not None:
            return Transition(
                state=next_state,
                action=action,
                terminal=True,
                termination=termination,
            )
        return Transition(state=next_state, action=action)

    def snapshot(self, state: ChessGameState) -> ArtifactPayload:
        from zugzwang_core.domain.canonical import canonical_json_string

        data = canonical_json_string(
            {
                "fen": state.fen,
                "initial_fen": state.initial_fen,
                "moves": list(state.move_stack),
                "variant": state.variant,
            }
        ).encode("utf-8")
        return ArtifactPayload(media_type=STATE_MEDIA_TYPE, data=data)

    def restore(self, snapshot: ArtifactPayload) -> ChessGameState:
        import json

        if snapshot.media_type != STATE_MEDIA_TYPE:
            raise EnvironmentError_(f"cannot restore chess state from {snapshot.media_type}")
        data = json.loads(snapshot.data.decode("utf-8"))
        return ChessGameState(
            fen=str(data["fen"]),
            initial_fen=str(data.get("initial_fen", START_FEN)),
            move_stack=tuple(str(m) for m in data.get("moves", [])),
            variant=str(data.get("variant", "standard")),
        )


class StandardChessEnvironmentDefinition:
    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="chess.standard",
            plugin_version="0.1.0",
            kind=PluginKind.ENVIRONMENT,
            capabilities=("snapshot", "restore", "legal_actions", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )
