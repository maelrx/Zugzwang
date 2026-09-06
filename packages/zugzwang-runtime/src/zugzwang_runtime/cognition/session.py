"""DecisionSession — the authorized surface of one decision (PRD §26.1; CB-WO-05).

The factory composes the decision journal, the CAS artifact plumbing and the
tool broker for a single decision. ``DecisionSession.open`` performs the
§12.2 opening (PREPARING→READY→ACTIVE): config artifact, state snapshots,
node bindings and the first round are all journaled before any tool call can
happen. The decision loop (CB-WO-07) consumes this session — it never touches
the journal tables directly.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import Engine

from zugzwang_chess.environment.standard import (
    START_FEN,
    STATE_MEDIA_TYPE,
    ChessGameState,
    StandardChessRulesKernel,
)
from zugzwang_core.domain.artifacts import ArtifactPayload, ArtifactRef
from zugzwang_core.domain.canonical import canonical_json_bytes
from zugzwang_core.domain.cognition import ToolEnvelope, position_key_v2, state_key_v2
from zugzwang_core.domain.errors import ArtifactError

from ..artifacts.cas import ContentAddressedStore
from ..persistence.cognition import CognitionJournal
from ..persistence.repositories import ArtifactRepository
from ..search.workspace import SearchWorkspace
from .broker import (
    ArtifactLoader,
    ArtifactSink,
    CognitionToolBroker,
    DecisionBudget,
    ToolOperationBudget,
)

if TYPE_CHECKING:
    from zugzwang_chess.cognition import ChessPerception

ROOT_ROUND_ID_SUFFIX = "round-0001"


@dataclass(frozen=True, slots=True)
class SessionComponents:
    """Decision-scoped components shared by every round's broker."""

    journal: CognitionJournal
    perception: Any
    cas: ContentAddressedStore
    engine: Engine
    sink: ArtifactSink
    loader: ArtifactLoader
    rules_kernel: StandardChessRulesKernel
    workspace: SearchWorkspace
    policy_hash: str
    max_batch: int
    max_argument_bytes: int
    search_session_id: str
    clock: Callable[[], str]


def _default_clock() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def cas_artifact_sink(
    cas: ContentAddressedStore, engine: Engine, clock: Callable[[], str]
) -> ArtifactSink:
    """CAS-coherent artifact sink: object first, then the registering row (§10.5).

    Content-addressed identity makes duplicate registration harmless (the row
    insert is OR IGNORE); a crash between CAS write and row insert can only
    create an orphan, never a dangling reference (NFR-003).
    """
    artifacts = ArtifactRepository(engine)

    def sink(data: bytes, media_type: str = "application/json") -> str:
        ref = cas.put(ArtifactPayload(media_type=media_type, data=data))
        artifacts.insert_artifact(
            row={
                "artifact_id": ref.as_id(),
                "algorithm": "sha256",
                "size_bytes": len(data),
                "media_type": media_type,
                "relative_path": ref.storage_path(),
                "created_at": clock(),
            }
        )
        return ref.as_id()

    return sink


def cas_artifact_loader(cas: ContentAddressedStore) -> ArtifactLoader:
    """Read a registered artifact back from the CAS (integrity-checked)."""

    def load(artifact_id: str) -> bytes | None:
        try:
            ref = ArtifactRef.parse(artifact_id)
        except ArtifactError:
            return None
        if not cas.exists(ref):
            return None
        return cas.get(ref).data

    return load


def _is_legal_ep(board: Any, ep_square: str) -> bool:
    """A fen ep square enters the position key only when a legal en-passant
    capture actually exists (§7.4; same rule as the perception)."""
    import chess

    target = chess.parse_square(ep_square)
    return any(move.to_square == target and board.is_en_passant(move) for move in board.legal_moves)


def identity_keys(state: ChessGameState) -> tuple[str, str]:
    """(state_key, position_key) of a node's state (§7.2).

    Mirrors the perception's packet identity derivation; promoting this to the
    StateIdentityPort implementation is follow-up work outside ZGW-0092's
    allowed paths.
    """
    board = state.to_board()
    parts = state.fen.split(" ")
    placement = parts[0]
    side = parts[1] if len(parts) > 1 else "w"
    castling = parts[2] if len(parts) > 2 else "-"
    ep = parts[3] if len(parts) > 3 else "-"
    ep_legal = ep if (ep != "-" and _is_legal_ep(board, ep)) else "-"
    return (
        state_key_v2(state.fingerprint(), state.variant, "standard-rules/v1"),
        position_key_v2(placement, side, castling, ep_legal),
    )


def _state_record(state: ChessGameState) -> dict[str, Any]:
    """Canonical serial form of the integral state (design §14.2)."""
    return {
        "fen": state.fen,
        "initial_fen": state.initial_fen,
        "move_stack": list(state.move_stack),
        "variant": state.variant,
        "synthetic_clock": state.synthetic_clock,
    }


class DecisionSession:
    """One decision's authorized surface: journal + perception + broker (§26.1)."""

    _factory: SessionComponents | None = None
    _interaction_mode: str = "native_tools"
    _model_reservation_id: str | None = None
    memory_store: Any | None = None
    skill_registry: Any | None = None
    plan_store: Any | None = None

    def __init__(
        self,
        *,
        decision_id: str,
        broker: CognitionToolBroker,
        journal: CognitionJournal,
    ) -> None:
        self.decision_id = decision_id
        self._broker = broker
        self._journal = journal

    def execute(
        self, tool: str, arguments: dict[str, Any], *, idempotency_key: str
    ) -> ToolEnvelope:
        """Run one tool through the broker (the only authorized path, §38.6)."""
        return self._broker.execute(tool, arguments, idempotency_key=idempotency_key)

    @property
    def bound_node_ids(self) -> list[str]:
        return self._journal.bound_node_ids(self.decision_id)

    @property
    def journal(self) -> CognitionJournal:
        return self._journal

    @property
    def workspace(self) -> SearchWorkspace | None:
        return self._broker.workspace

    @property
    def root_node_id(self) -> str | None:
        return self._broker.root_node_id

    @property
    def interaction_mode(self) -> str:
        """native_tools or json_commands, frozen at decision open (§12.1)."""
        return self._interaction_mode

    @property
    def model_reservation_id(self) -> str | None:
        """Ledger reservation of the model-calls unit (None when unbounded)."""
        return self._model_reservation_id

    @property
    def budget(self) -> ToolOperationBudget:
        """The decision's budget authority (multi-unit, decision-scoped)."""
        return self._broker.budget

    def round_context_artifact_id(self, ordinal: int, request: Any) -> str:
        """CAS-artifact the EXACT model request of one round (§22.1/FR-020).

        The round's context row points at the canonical request bytes, so the
        timeline shows what the model actually received — not a summary.
        """
        factory = self._factory
        if factory is None:
            raise ValueError("session was not opened through DecisionSession.open")
        payload = canonical_json_bytes({"request": json.loads(request.model_dump_json())})
        return factory.sink(payload, "application/vnd.zugzwang.model-request+json")

    @classmethod
    def open(
        cls,
        *,
        decision_id: str,
        step_id: str,
        decision_ordinal: int,
        search_session_id: str,
        strategy_id: str,
        strategy_version: str,
        interaction_mode: str,
        policy_hash: str,
        config: dict[str, Any],
        states: dict[str, ChessGameState],
        journal: CognitionJournal,
        perception: ChessPerception,
        cas: ContentAddressedStore,
        engine: Engine,
        clock: Callable[[], str] | None = None,
        max_batch: int = 16,
        max_argument_bytes: int = 8192,
        remaining_tool_operations: int = 32,
        max_depth_plies: int = 6,
        max_nodes: int = 64,
        max_model_calls: int = 0,
    ) -> DecisionSession:
        """Open a decision: journal the opening, then expose the broker (§26.1)."""
        clock = clock or _default_clock
        sink = cas_artifact_sink(cas, engine, clock)
        loader = cas_artifact_loader(cas)

        node_ids = list(states)
        if not node_ids:
            raise ValueError("a decision session requires at least the root node")
        root_node_id = node_ids[0]
        node_keys = {node_id: identity_keys(state) for node_id, state in states.items()}
        root_state_key, root_position_key = node_keys[root_node_id]

        rules_kernel = StandardChessRulesKernel()
        workspace = SearchWorkspace(
            kernel=rules_kernel,
            root_state=states[root_node_id],
            session_id=search_session_id,
            max_depth_plies=max_depth_plies,
            max_nodes=max_nodes,
        )
        # Every bound initial node must exist in the search-graph projection:
        # cb_node_bindings references search_nodes with a session scope guard.
        for node_id, state in states.items():
            state_key, position_key = node_keys[node_id]
            journal.ensure_search_node(
                node_id=node_id,
                search_session_id=search_session_id,
                parent_id=None,
                position_key=position_key,
                trajectory_key=f"anchor:{state_key}",
                state_ref=f"decision://{decision_id}/{node_id}",
                action_from_parent=None,
                root_action=None,
                depth=_depth_plies(state),
                side_to_move=state.side_to_move,
                terminal=state.termination is not None,
                created_by="root",
                status="terminal" if state.termination is not None else "frontier",
            )

        journal.ensure_state_snapshot(
            state_key=root_state_key,
            state_schema_version="state/v2",
            rules_version="standard/v1",
            variant=states[root_node_id].variant,
            position_key=root_position_key,
            history_completeness=_history_completeness(states[root_node_id]),
            state_artifact_id=sink(
                _canonical(_state_record(states[root_node_id])), STATE_MEDIA_TYPE
            ),
        )
        config_artifact_id = sink(_canonical(config), "application/json")
        journal.create_decision(
            decision_id=decision_id,
            step_id=step_id,
            decision_ordinal=decision_ordinal,
            search_session_id=search_session_id,
            root_state_key=root_state_key,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            interaction_mode=interaction_mode,
            policy_hash=policy_hash,
            config_artifact_id=config_artifact_id,
        )
        # Decision-scoped budget reservations (§13; INV-06): distinct units,
        # one authority per decision — branching/focus never re-creates them.
        tool_reservation_id = f"bres:{decision_id}:tool_operations"
        journal.reserve_budget(
            reservation_id=tool_reservation_id,
            decision_id=decision_id,
            owner_kind="tool_operation",
            owner_id=decision_id,
            unit="tool_operations",
            amount=remaining_tool_operations,
            evidence_artifact_id=config_artifact_id,
        )
        model_reservation_id: str | None = None
        if max_model_calls > 0:
            model_reservation_id = f"bres:{decision_id}:model_calls"
            journal.reserve_budget(
                reservation_id=model_reservation_id,
                decision_id=decision_id,
                owner_kind="finalization",
                owner_id=decision_id,
                unit="model_calls",
                amount=max_model_calls,
                evidence_artifact_id=config_artifact_id,
            )
        journal.transition_decision(decision_id, "READY")
        journal.transition_decision(decision_id, "ACTIVE")

        for sequence, (node_id, state) in enumerate(states.items()):
            state_key, _position_key = node_keys[node_id]
            journal.ensure_state_snapshot(
                state_key=state_key,
                state_schema_version="state/v2",
                rules_version="standard/v1",
                variant=state.variant,
                position_key=node_keys[node_id][1],
                history_completeness=_history_completeness(state),
                state_artifact_id=sink(_canonical(_state_record(state)), STATE_MEDIA_TYPE),
            )
            journal.bind_node(
                decision_id=decision_id,
                node_id=node_id,
                state_key=state_key,
                depth_plies=_depth_plies(state),
                created_sequence=sequence,
            )

        # Round 0001 is the decision OPENING record (§12.2: journaled before
        # any tool call). The loop creates every subsequent round with the
        # EXACT ModelRequest as its context (FR-020/§22.1; cb_rounds context
        # is immutable by trigger, so it must be submitted at creation).
        round_context_artifact_id = sink(
            _canonical({"root_state_key": root_state_key, "purpose": "open"}),
            "application/json",
        )
        journal.add_round(
            round_id=f"{decision_id}:{ROOT_ROUND_ID_SUFFIX}",
            decision_id=decision_id,
            ordinal=1,
            purpose="explore",
            context_artifact_id=round_context_artifact_id,
        )

        broker = CognitionToolBroker(
            decision_id=decision_id,
            round_id=f"{decision_id}:{ROOT_ROUND_ID_SUFFIX}",
            round_ordinal=1,
            journal=journal,
            perception=perception,
            policy_hash=policy_hash,
            states=dict(states),
            budget=DecisionBudget(
                tool_operations=remaining_tool_operations, model_calls=max_model_calls
            ),
            artifact_sink=sink,
            artifact_loader=loader,
            max_batch=max_batch,
            max_argument_bytes=max_argument_bytes,
            rules_kernel=rules_kernel,
            search_workspace=workspace,
            search_session_id=search_session_id,
            budget_reservation_id=tool_reservation_id,
        )
        session = cls(decision_id=decision_id, broker=broker, journal=journal)
        session._model_reservation_id = model_reservation_id
        session._interaction_mode = interaction_mode
        session._factory = SessionComponents(
            journal=journal,
            perception=perception,
            cas=cas,
            engine=engine,
            sink=sink,
            loader=loader,
            rules_kernel=rules_kernel,
            workspace=workspace,
            policy_hash=policy_hash,
            max_batch=max_batch,
            max_argument_bytes=max_argument_bytes,
            search_session_id=search_session_id,
            clock=clock,
        )
        return session

    def attach_components(self, components: SessionComponents) -> None:
        """Bind decision-scoped components on a RESUMED session (§14.4)."""
        self._factory = components

    def new_broker_for_round(self, round_id: str, ordinal: int) -> CognitionToolBroker:
        """Broker for a later round sharing this decision's graph and budget.

        Rounds are journal boundaries; the workspace, the kernel, the states
        reached so far and the tool-operation pool are decision-scoped and
        must never reset between rounds (§9.1, TEST-031).
        """
        factory = self._factory
        if factory is None:
            raise ValueError("session was not opened through DecisionSession.open")
        return self._broker.round_broker(round_id, ordinal)


def _canonical(payload: dict[str, Any]) -> bytes:
    return canonical_json_bytes(payload)


def _history_completeness(state: ChessGameState) -> str:
    """'complete' only when the full game history is anchored at the standard start."""
    return "complete" if state.initial_fen == START_FEN else "from_anchor"


def _depth_plies(state: ChessGameState) -> int:
    return len(state.move_stack)
