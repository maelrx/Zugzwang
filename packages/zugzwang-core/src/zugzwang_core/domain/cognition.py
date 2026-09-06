"""CognitiveBoard decision contracts (PRD §7.2, §12.2, §15, §26, §42).

Strict DTOs for the CognitiveBoard decision layer: identity keys with distinct
semantics, the tool envelope with the error catalogue, the decision state
machine, the resolved decision manifest and the bounded configuration. All
models are frozen and forbid unknown fields; identity keys are built from
canonical JSON + SHA-256 so equal semantics always hash identically.

This module is contract-only: no chess, runtime or provider imports.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .canonical import canonical_json_bytes

COGNITION_CONTRACT_VERSION = Literal[2]


def _key(kind: str, version: int, *parts: str) -> str:
    """Deterministic key: kind prefix + version + sha256 over canonical parts.

    Equal semantics always produce the same key; any difference in the labelled
    parts (including a part's absence) changes the hash. The version is hashed
    with the parts so a scheme bump never collides with old keys.
    """
    payload = {"kind": kind, "version": version, "parts": list(parts)}
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"{kind}:v{version}:{digest[:32]}"


# ---------------------------------------------------------------------------
# §7.2 — identifiers with distinct semantics
# ---------------------------------------------------------------------------


def state_key_v2(integral_state: str, variant: str, rules_context: str, version: int = 2) -> str:
    """Integral normalized state + variant + rules context + scheme version."""
    return _key("state_key", version, integral_state, variant, rules_context)


def position_key_v2(
    placement: str, side_to_move: str, castling_rights: str, legal_en_passant: str
) -> str:
    """Equivalent-position projection: placement, side, castling, legal ep."""
    return _key(
        "position_key",
        2,
        placement,
        side_to_move,
        castling_rights,
        legal_en_passant,
    )


def trajectory_key_v2(root_state_key: str, actions: tuple[str, ...], context: str) -> str:
    """Root state + ordered action sequence + context (path of analysis)."""
    return _key("trajectory_key", 2, root_state_key, *actions, context)


def node_id_v2(session_id: str, trajectory_key: str) -> str:
    """Address of one trajectory occurrence inside one decision session."""
    return _key("node_id", 2, session_id, trajectory_key)


def action_id_v2(state_key: str, uci: str, action_schema_version: str, policy_hash: str) -> str:
    """State-bound action identity: prevents use in the wrong state."""
    return _key("action_id", 2, state_key, uci, action_schema_version, policy_hash)


def packet_content_hash_v2(packet: dict[str, Any]) -> str:
    """Semantic packet content (no timestamps, no telemetry)."""
    return _key("packet_content_hash", 2, canonical_json_bytes(packet).decode("utf-8"))


def observation_id_v2(packet_content_hash: str, round_no: int, exposure: int) -> str:
    """One concrete exposure of a packet to the model (causality/transcript)."""
    return _key("observation_id", 2, packet_content_hash, str(round_no), str(exposure))


def operation_id_v2(decision_id: str, round_no: int, call_id: str) -> str:
    """Decision + round + tool call id (idempotent local effect)."""
    return _key("operation_id", 2, decision_id, str(round_no), call_id)


# ---------------------------------------------------------------------------
# §15.1/§15.2 — error catalogue and retry policy
# ---------------------------------------------------------------------------


class ToolErrorCategory(StrEnum):
    """Category of a tool error (PRD §15.1)."""

    CONTRACT = "contract"
    SAFETY = "safety"
    EXPOSURE = "exposure"
    INTEGRITY = "integrity"
    STATE = "state"
    FORMAL = "formal"
    BUDGET = "budget"
    OPERATIONAL = "operational"
    PROVENANCE = "provenance"
    COMPATIBILITY = "compatibility"
    TRANSPORT = "transport"
    INFRASTRUCTURE = "infrastructure"
    IMPLEMENTATION = "implementation"


class RetryClass(StrEnum):
    """Loop effect of an error (PRD §15.1 'Efeito no loop' + §15.2)."""

    REPAIR_ALLOWED = "repair_allowed"  # consumes a logical op; model may correct
    NO_EXECUTION_AUDITED = "no_execution_audited"  # never executed; always audited
    WITHHOLD_FACT = "withhold_fact"  # refuse without leaking the forbidden fact
    REJECT_MAY_END = "reject_may_end"  # rejection; repeated pattern may end decision
    REQUEST_CORRECT_INPUT = "request_correct_input"  # ask for the right observation
    NO_CHILD = "no_child"  # formal: no child node is produced
    NO_TRANSITION = "no_transition"  # formal: node already terminal
    REDUCE_OR_FINALIZE = "reduce_or_finalize"  # shrink the batch or finish
    COMPACT_OR_FINALIZE = "compact_or_finalize"  # compact by policy or finish
    FAIL_CLOSED = "fail_closed"  # hard failure of the decision
    PAUSE_OR_EXPLICIT_RETRY = "pause_or_explicit_retry"  # ambiguous outcome only
    NO_EFFECT_ACKNOWLEDGED = "no_effect_acknowledged"  # do not claim the effect
    NO_PARTIAL_OUTPUT = "no_partial_output"  # never expose partial output


ERROR_CATALOGUE: dict[str, tuple[ToolErrorCategory, RetryClass]] = {
    "INVALID_ARGUMENTS": (ToolErrorCategory.CONTRACT, RetryClass.REPAIR_ALLOWED),
    "TOOL_NOT_ALLOWED": (ToolErrorCategory.SAFETY, RetryClass.NO_EXECUTION_AUDITED),
    "CAPABILITY_DENIED": (ToolErrorCategory.EXPOSURE, RetryClass.WITHHOLD_FACT),
    "NODE_SCOPE_MISMATCH": (ToolErrorCategory.INTEGRITY, RetryClass.REJECT_MAY_END),
    "ACTION_STATE_MISMATCH": (ToolErrorCategory.STATE, RetryClass.REQUEST_CORRECT_INPUT),
    "ILLEGAL_ACTION": (ToolErrorCategory.FORMAL, RetryClass.NO_CHILD),
    "TERMINAL_NODE": (ToolErrorCategory.FORMAL, RetryClass.NO_TRANSITION),
    "DEPTH_LIMIT": (ToolErrorCategory.BUDGET, RetryClass.REDUCE_OR_FINALIZE),
    "BUDGET_INSUFFICIENT": (ToolErrorCategory.BUDGET, RetryClass.REDUCE_OR_FINALIZE),
    "CONTEXT_LIMIT": (ToolErrorCategory.OPERATIONAL, RetryClass.COMPACT_OR_FINALIZE),
    "SOURCE_NOT_ALLOWED": (ToolErrorCategory.PROVENANCE, RetryClass.WITHHOLD_FACT),
    "STATE_REPLAY_MISMATCH": (ToolErrorCategory.INTEGRITY, RetryClass.FAIL_CLOSED),
    "SEMANTICS_MISMATCH": (ToolErrorCategory.COMPATIBILITY, RetryClass.NO_PARTIAL_OUTPUT),
    "PROVIDER_OUTCOME_UNKNOWN": (ToolErrorCategory.TRANSPORT, RetryClass.PAUSE_OR_EXPLICIT_RETRY),
    "PERSISTENCE_FAILED": (ToolErrorCategory.INFRASTRUCTURE, RetryClass.NO_EFFECT_ACKNOWLEDGED),
    "OUTPUT_CONTRACT_VIOLATION": (
        ToolErrorCategory.IMPLEMENTATION,
        RetryClass.NO_PARTIAL_OUTPUT,
    ),
}

TOOL_ERROR_CODES = frozenset(ERROR_CATALOGUE)
DEFAULT_MAX_PROTOCOL_ERRORS = 3


class ToolError(BaseModel):
    """One error result inside a tool envelope (PRD §15.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    category: ToolErrorCategory
    retry_class: RetryClass
    details: dict[str, Any] = {}

    @classmethod
    def build(cls, code: str, message: str, details: dict[str, Any] | None = None) -> ToolError:
        """Build from the catalogue; unknown codes are a contract error."""
        if code not in ERROR_CATALOGUE:
            raise ValueError(
                f"unknown tool error code {code!r}; expected one of {TOOL_ERROR_CODES}"
            )
        category, retry_class = ERROR_CATALOGUE[code]
        return cls(
            code=code,
            message=message,
            category=category,
            retry_class=retry_class,
            details=details or {},
        )


# ---------------------------------------------------------------------------
# §42.6 — normalized tool envelope
# ---------------------------------------------------------------------------


class ToolRequest(BaseModel):
    """Normalized tool call issued by the model inside one round."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str = Field(min_length=8)
    decision_id: str = Field(min_length=4)
    round_no: int = Field(ge=0)
    tool: str = Field(min_length=1)
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Normalized tool outcome: payload or catalogue error, never both."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str = Field(min_length=8)
    ok: bool
    payload: dict[str, Any] | None = None
    error: ToolError | None = None
    duration_ms: int | None = Field(default=None, ge=0)

    @classmethod
    def success(cls, operation_id: str, payload: dict[str, Any]) -> ToolResult:
        return cls(operation_id=operation_id, ok=True, payload=payload)

    @classmethod
    def failure(cls, operation_id: str, error: ToolError) -> ToolResult:
        return cls(operation_id=operation_id, ok=False, error=error)


class ToolEnvelope(BaseModel):
    """Request + result pair for one idempotent operation (PRD §42.6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: ToolRequest
    result: ToolResult

    def model_post_init(self, __context: Any) -> None:
        if self.request.operation_id != self.result.operation_id:
            raise ValueError("envelope operation_id mismatch between request and result")
        if self.result.ok and self.result.error is not None:
            raise ValueError("successful result must not carry an error")
        if not self.result.ok and self.result.error is None:
            raise ValueError("failed result must carry a catalogue error")
        if not self.result.ok and self.result.payload is not None:
            raise ValueError("failed result must not carry a payload")


# ---------------------------------------------------------------------------
# §12.2 — decision state machine
# ---------------------------------------------------------------------------


class DecisionStatus(StrEnum):
    """Aggregated decision lifecycle (PRD §12.2, cb_decisions.status)."""

    PREPARING = "PREPARING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    PAUSED = "PAUSED"
    SELECTED = "SELECTED"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DecisionPhase(StrEnum):
    """Internal controller phases; all map to the ACTIVE aggregate."""

    PREPARING = "PREPARING"
    READY = "READY"
    REQUEST_PENDING = "REQUEST_PENDING"
    RESPONSE_COMMITTED = "RESPONSE_COMMITTED"
    TOOL_EXECUTING = "TOOL_EXECUTING"
    ROUND_COMMITTED = "ROUND_COMMITTED"
    FINALIZING = "FINALIZING"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    PAUSED = "PAUSED"
    SELECTED = "SELECTED"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


INTERNAL_ACTIVE_PHASES = frozenset(
    {
        DecisionPhase.REQUEST_PENDING,
        DecisionPhase.RESPONSE_COMMITTED,
        DecisionPhase.TOOL_EXECUTING,
        DecisionPhase.ROUND_COMMITTED,
        DecisionPhase.FINALIZING,
    }
)

_LEGAL_TRANSITIONS: dict[DecisionPhase, frozenset[DecisionPhase]] = {
    DecisionPhase.PREPARING: frozenset({DecisionPhase.READY, DecisionPhase.FAILED}),
    DecisionPhase.READY: frozenset({DecisionPhase.REQUEST_PENDING, DecisionPhase.CANCELLED}),
    DecisionPhase.REQUEST_PENDING: frozenset(
        {DecisionPhase.RESPONSE_COMMITTED, DecisionPhase.OUTCOME_UNKNOWN, DecisionPhase.FAILED}
    ),
    DecisionPhase.RESPONSE_COMMITTED: frozenset(
        {DecisionPhase.TOOL_EXECUTING, DecisionPhase.FINALIZING}
    ),
    DecisionPhase.TOOL_EXECUTING: frozenset({DecisionPhase.ROUND_COMMITTED}),
    DecisionPhase.ROUND_COMMITTED: frozenset({DecisionPhase.READY, DecisionPhase.FINALIZING}),
    DecisionPhase.FINALIZING: frozenset({DecisionPhase.SELECTED, DecisionPhase.FAILED}),
    DecisionPhase.OUTCOME_UNKNOWN: frozenset({DecisionPhase.READY, DecisionPhase.PAUSED}),
    DecisionPhase.PAUSED: frozenset(),
    DecisionPhase.SELECTED: frozenset({DecisionPhase.COMMITTED}),
    DecisionPhase.COMMITTED: frozenset(),
    DecisionPhase.FAILED: frozenset(),
    DecisionPhase.CANCELLED: frozenset(),
}

LEGAL_TRANSITIONS = dict(_LEGAL_TRANSITIONS)


def decision_aggregate(phase: DecisionPhase) -> DecisionStatus:
    """Map an internal phase to its aggregated lifecycle status (§12.2)."""
    if phase in INTERNAL_ACTIVE_PHASES:
        return DecisionStatus.ACTIVE
    return DecisionStatus(phase.value)


def can_transition(current: DecisionPhase, target: DecisionPhase) -> bool:
    """True only for transitions present in the §12.2 state diagram."""
    return target in LEGAL_TRANSITIONS[current]


# ---------------------------------------------------------------------------
# §26/§13 — bounded decision manifest and configuration
# ---------------------------------------------------------------------------


class _DecisionManifestFields(BaseModel):
    """Manifest fields without the hash; the hash input is their JSON form."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=4)
    contract_version: COGNITION_CONTRACT_VERSION = 2
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    model_ref: str = Field(min_length=1)
    seed: int
    tool_registry: tuple[str, ...] = ()
    max_rounds: int = Field(ge=1)
    max_protocol_errors: int = Field(ge=1, default=DEFAULT_MAX_PROTOCOL_ERRORS)
    feature_flags: frozenset[str] = frozenset()


class DecisionManifest(BaseModel):
    """Resolved per-decision manifest with canonical content hash (§38.3).

    The hash is computed over the JSON contract representation of the fields
    (model_dump(mode="json")), so it is a pure function of the contract —
    independent of the Python container types used at the call site.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=4)
    contract_version: COGNITION_CONTRACT_VERSION = 2
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    model_ref: str = Field(min_length=1)
    seed: int
    tool_registry: tuple[str, ...] = ()
    max_rounds: int = Field(ge=1)
    max_protocol_errors: int = Field(ge=1, default=DEFAULT_MAX_PROTOCOL_ERRORS)
    feature_flags: frozenset[str] = frozenset()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def build(cls, **fields: Any) -> DecisionManifest:
        """Build with the content hash over the canonical manifest fields."""
        fields = {k: v for k, v in fields.items() if k != "content_sha256"}
        draft = _DecisionManifestFields.model_validate(fields).model_dump(mode="json")
        digest = hashlib.sha256(canonical_json_bytes(draft)).hexdigest()
        return cls(**draft, content_sha256=digest)


class CognitiveBoardConfig(BaseModel):
    """Bounded configuration; conservative defaults per PRD §48.3.

    Feature flags are all off by default (G-CB-08: reanchoring, parallelism
    and visual stay disabled until ratified and capability-tested).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: COGNITION_CONTRACT_VERSION = 2
    max_rounds: int = Field(ge=1, default=8)
    max_protocol_errors: int = Field(ge=1, default=DEFAULT_MAX_PROTOCOL_ERRORS)
    enable_reanchoring: bool = False
    enable_parallelism: bool = False
    enable_visual: bool = False
    enable_skills: bool = False
