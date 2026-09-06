"""PositionPacket DTOs (PRD §8.2).

The full packet exists internally; a tool response is an authorized projection.
Disabled fields are absent — never replaced by an equivalent summary. Execution
metadata (operation_id, observed_at, cost, remaining budget) lives in the outer
envelope so the semantic hash never depends on the clock.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from zugzwang_core.domain.cognition import action_id_v2, packet_content_hash_v2

PACKET_SCHEMA_VERSION = "zgw.position-packet/v1"
RELATIONS_SEMANTICS_VERSION = "l0r-minimal/v1"


class PacketState(BaseModel):
    """Integral-state identity block (§8.2 'state')."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_key: str = Field(min_length=8)
    node_id: str = Field(min_length=1)
    variant: str = "standard"
    side_to_move: str
    history_completeness: Literal["full", "from_anchor"]


class PacketRepresentation(BaseModel):
    """Authorized representation fields; disabled fields are absent (None)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fen: str | None = None
    piece_map: dict[str, str] | None = None
    image_ref: str | None = None


class CognitionError(Exception):
    """Contract error with machine code (CODING_STANDARDS / Errors)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ActionStateMismatch(CognitionError):
    """An action key was used against a state it is not bound to (§15.1)."""

    def __init__(self, message: str) -> None:
        super().__init__("ACTION_STATE_MISMATCH", message)


class LegalActionItem(BaseModel):
    """One action as an object, bound to the packet's state key (§8.3).

    Formal descriptors only: squares, piece, capture/castling/promotion flags.
    No SAN annotation (TEST-007 belongs to the exposure broker, CB-WO-05).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    uci: str = Field(min_length=4)
    action_id: str = Field(min_length=8)
    from_square: str = Field(min_length=2)
    to_square: str = Field(min_length=2)
    piece: str = Field(min_length=1)
    is_capture: bool = False
    is_castling: bool = False
    promotion: str | None = None

    @classmethod
    def build(
        cls,
        index: int,
        uci: str,
        state_key: str,
        action_schema_version: str,
        policy_hash: str,
        *,
        from_square: str,
        to_square: str,
        piece: str,
        is_capture: bool = False,
        is_castling: bool = False,
        promotion: str | None = None,
    ) -> LegalActionItem:
        return cls(
            index=index,
            uci=uci,
            action_id=action_id_v2(state_key, uci, action_schema_version, policy_hash),
            from_square=from_square,
            to_square=to_square,
            piece=piece,
            is_capture=is_capture,
            is_castling=is_castling,
            promotion=promotion,
        )


def require_action_belongs(
    state_key: str,
    item: LegalActionItem,
    action_schema_version: str,
    policy_hash: str,
) -> None:
    """Raise ACTION_STATE_MISMATCH when the action is not bound to this state."""
    expected = action_id_v2(state_key, item.uci, action_schema_version, policy_hash)
    if item.action_id != expected:
        raise ActionStateMismatch("action does not belong to this state")


class PacketLegalActions(BaseModel):
    """Paginated legal set; pages recompose exactly the kernel set (§TEST-005)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_count: int = Field(ge=0)
    set_hash: str = Field(min_length=8)
    ordering: str
    items: tuple[LegalActionItem, ...]
    next_cursor: int | None = None
    complete: bool


class PacketRelations(BaseModel):
    """L0-R minimal formal relations (§8.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantics_version: str = RELATIONS_SEMANTICS_VERSION
    requested_scope: str
    items: tuple[dict[str, str | int], ...]
    complete: bool


class PacketTerminal(BaseModel):
    """Automatic termination facts; claims are never automatic (§8.7)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    automatic: bool
    kind: str | None = None
    result: str | None = None
    claim_policy: str | None = None


class PacketProvenance(BaseModel):
    """Rules and perception versions + exposure policy hash (§8.2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rules_version: str
    perception_version: str
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PositionPacket(BaseModel):
    """The L0 packet: deterministic facts about one node (PRD §8.2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["zgw.position-packet/v1"] = "zgw.position-packet/v1"
    state: PacketState
    representation: PacketRepresentation
    legal_actions: PacketLegalActions
    relations: PacketRelations
    terminal: PacketTerminal
    provenance: PacketProvenance

    def content_hash(self) -> str:
        """Semantic content hash (packet_content_hash_v2, no telemetry)."""
        return packet_content_hash_v2(self.model_dump(mode="json"))
