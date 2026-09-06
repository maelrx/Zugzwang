"""CognitiveBoard decision contracts (PRD §7.2, §12.2, §15, §26, §42.6).

Strict DTOs for the CognitiveBoard decision layer: identity keys with distinct
semantics, the §42.6 tool-result envelope with the §15.1 error catalogue, the
§12.2 decision state machine, the resolved decision manifest and the bounded
configuration. All models are frozen and forbid unknown fields; identity keys
are built from canonical JSON + full SHA-256 so equal semantics always hash
identically.

This module is contract-only: no chess, runtime or provider imports.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from .canonical import canonical_json_bytes

COGNITION_CONTRACT_VERSION = Literal[2]
ENVELOPE_SCHEMA_VERSION = Literal["zgw.cognitive-tool-result/v1"]

# Keys stripped from packet content before hashing (PRD §7.2: the content hash
# covers the semantic packet content, "sem timestamp/telemetria").
TELEMETRY_KEYS = frozenset({"timestamp", "telemetry", "observed_at", "wall_clock_ms"})

_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9:_-]{0,127}$"


def _key(kind: str, version: int, *parts: str) -> str:
    """Deterministic key: kind prefix + version + full sha256 over canonical parts.

    Equal semantics always produce the same key; any difference in the labelled
    parts (including a part's absence) changes the hash. The version is hashed
    with the parts so a scheme bump never collides with old keys.
    """
    payload = {"kind": kind, "version": version, "parts": list(parts)}
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"{kind}:v{version}:{digest}"


def _strip_telemetry(value: Any) -> Any:
    """Recursively remove reserved telemetry keys from a JSON-like value."""
    if isinstance(value, dict):
        mapping = cast(dict[str, Any], value)
        entries: list[tuple[str, Any]] = list(mapping.items())
        return {k: _strip_telemetry(v) for k, v in entries if k not in TELEMETRY_KEYS}
    if isinstance(value, list):
        return [_strip_telemetry(v) for v in cast(list[Any], value)]
    return value


# ---------------------------------------------------------------------------
# §7.2 — identifiers with distinct semantics
# ---------------------------------------------------------------------------


def state_key_v2(integral_state: str, variant: str, rules_context: str, version: int = 2) -> str:
    """Integral normalized state + variant + rules context + scheme version."""
    return _key("state_key", version, integral_state, variant, rules_context)


def position_key_v2(
    placement: str, side_to_move: str, castling_rights: str, legal_en_passant: str
) -> str:
    """Equivalent-position projection (PRD §7.4: only the normalized legal
    en-passant opportunity enters the key — normalization of the opportunity
    itself is the caller's perception concern, CB-WO-03)."""
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
    """State-bound action identity (state_key + UCI + rules/action-schema +
    policy/lease hash) — prevents use in the wrong state."""
    return _key("action_id", 2, state_key, uci, action_schema_version, policy_hash)


def packet_content_hash_v2(packet: dict[str, Any]) -> str:
    """Semantic packet content hash: reserved telemetry keys (TELEMETRY_KEYS)
    are stripped recursively before hashing, per §7.2."""
    return _key(
        "packet_content_hash",
        2,
        canonical_json_bytes(_strip_telemetry(packet)).decode("utf-8"),
    )


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
    """Loop effect of an error — one class per §15.1 'Efeito no loop'."""

    REPAIR_ALLOWED = "repair_allowed"  # consumes a logical op; model may correct
    NO_EXECUTION_AUDITED = "no_execution_audited"  # never executed; always audited
    WITHHOLD_FACT = "withhold_fact"  # refuse without leaking the forbidden fact
    REJECT_MAY_END = "reject_may_end"  # rejection; repeated pattern may end decision
    REQUEST_CORRECT_INPUT = "request_correct_input"  # ask for the right observation
    NO_CHILD = "no_child"  # formal: no child node is produced
    NO_TRANSITION = "no_transition"  # formal: node already terminal
    EXPLORE_ELSEWHERE = "explore_elsewhere"  # depth limit: explore another node
    REDUCE_OR_FINALIZE = "reduce_or_finalize"  # budget: shrink batch or finish
    COMPACT_OR_FINALIZE = "compact_or_finalize"  # compact by policy or finish
    FAIL_CLOSED = "fail_closed"  # hard failure of the decision
    PAUSE_OR_EXPLICIT_RETRY = "pause_or_explicit_retry"  # ambiguous outcome only
    NO_EFFECT_ACKNOWLEDGED = "no_effect_acknowledged"  # do not claim the effect
    REDESIGN_OR_FAIL = "redesign_or_fail"  # incompatible version: reproject or fail
    NO_PARTIAL_OUTPUT = "no_partial_output"  # never expose partial output


ERROR_CATALOGUE: dict[str, tuple[ToolErrorCategory, RetryClass]] = {
    "INVALID_ARGUMENTS": (ToolErrorCategory.CONTRACT, RetryClass.REPAIR_ALLOWED),
    "TOOL_NOT_ALLOWED": (ToolErrorCategory.SAFETY, RetryClass.NO_EXECUTION_AUDITED),
    "CAPABILITY_DENIED": (ToolErrorCategory.EXPOSURE, RetryClass.WITHHOLD_FACT),
    "NODE_SCOPE_MISMATCH": (ToolErrorCategory.INTEGRITY, RetryClass.REJECT_MAY_END),
    "ACTION_STATE_MISMATCH": (ToolErrorCategory.STATE, RetryClass.REQUEST_CORRECT_INPUT),
    "ILLEGAL_ACTION": (ToolErrorCategory.FORMAL, RetryClass.NO_CHILD),
    "TERMINAL_NODE": (ToolErrorCategory.FORMAL, RetryClass.NO_TRANSITION),
    "DEPTH_LIMIT": (ToolErrorCategory.BUDGET, RetryClass.EXPLORE_ELSEWHERE),
    "BUDGET_INSUFFICIENT": (ToolErrorCategory.BUDGET, RetryClass.REDUCE_OR_FINALIZE),
    "CONTEXT_LIMIT": (ToolErrorCategory.OPERATIONAL, RetryClass.COMPACT_OR_FINALIZE),
    "SOURCE_NOT_ALLOWED": (ToolErrorCategory.PROVENANCE, RetryClass.WITHHOLD_FACT),
    "STATE_REPLAY_MISMATCH": (ToolErrorCategory.INTEGRITY, RetryClass.FAIL_CLOSED),
    "SEMANTICS_MISMATCH": (ToolErrorCategory.COMPATIBILITY, RetryClass.REDESIGN_OR_FAIL),
    "PROVIDER_OUTCOME_UNKNOWN": (ToolErrorCategory.TRANSPORT, RetryClass.PAUSE_OR_EXPLICIT_RETRY),
    "PERSISTENCE_FAILED": (ToolErrorCategory.INFRASTRUCTURE, RetryClass.NO_EFFECT_ACKNOWLEDGED),
    "OUTPUT_CONTRACT_VIOLATION": (
        ToolErrorCategory.IMPLEMENTATION,
        RetryClass.NO_PARTIAL_OUTPUT,
    ),
}

TOOL_ERROR_CODES = frozenset(ERROR_CATALOGUE)

# §15.1/§15.2: the only feedback codes under which the loop may retry the same
# operation under an explicit policy (protocol errors are counted against
# ``max_protocol_errors``; everything else is terminal for the operation).
RETRYABLE_UNDER_POLICY = frozenset(
    {"INVALID_ARGUMENTS", "ACTION_STATE_MISMATCH", "PROVIDER_OUTCOME_UNKNOWN"}
)


class ToolError(BaseModel):
    """Envelope error (PRD §42.6): code from the §15.1 catalogue only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    retryable_under_policy: bool

    @classmethod
    def build(cls, code: str, message: str) -> ToolError:
        """Build from the catalogue; unknown codes are a contract error."""
        if code not in ERROR_CATALOGUE:
            raise ValueError(
                f"unknown tool error code {code!r}; expected one of {TOOL_ERROR_CODES}"
            )
        return cls(
            code=code, message=message, retryable_under_policy=code in RETRYABLE_UNDER_POLICY
        )


# ---------------------------------------------------------------------------
# §42.6 — normalized tool-result envelope
# ---------------------------------------------------------------------------


class EnvelopeMeta(BaseModel):
    """Provenance and budget meta of one tool result (PRD §42.6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(pattern=_ID_PATTERN)
    round_id: str = Field(pattern=_ID_PATTERN)
    operation_id: str = Field(pattern=_ID_PATTERN)
    tool_call_id: str = Field(pattern=_ID_PATTERN)
    exposure_sequence: int = Field(ge=0)
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    logical_operations_charged: int = Field(ge=0)
    physical_rules_queries: int = Field(ge=0)
    remaining_model_calls: int = Field(ge=0)
    remaining_tool_operations: int = Field(ge=0)


class ToolEnvelope(BaseModel):
    """Normalized tool-result envelope (PRD §42.6).

    ``ok=True`` requires ``result`` and forbids ``error``; ``ok=False``
    requires a catalogue ``error`` and forbids ``result``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: ENVELOPE_SCHEMA_VERSION = "zgw.cognitive-tool-result/v1"
    ok: bool
    meta: EnvelopeMeta
    result: dict[str, Any] | None = None
    error: ToolError | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.ok:
            if self.error is not None:
                raise ValueError("successful envelope must not carry an error")
            if self.result is None:
                raise ValueError("successful envelope must carry a result")
        else:
            if self.error is None:
                raise ValueError("failed envelope must carry a catalogue error")
            if self.result is not None:
                raise ValueError("failed envelope must not carry a result")


class ToolRequest(BaseModel):
    """Normalized tool call issued by the model inside one round."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str = Field(pattern=_ID_PATTERN)
    decision_id: str = Field(pattern=_ID_PATTERN)
    round_no: int = Field(ge=0)
    tool: str = Field(min_length=1)
    arguments: dict[str, Any]


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
    """Internal controller phases; the five in INTERNAL_ACTIVE_PHASES map to
    the ACTIVE aggregate (PRD §12.2). CANCELLED is an explicit aggregate set
    by the operator — no agent transition enters it."""

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

# Exactly the edges of the §12.2 state diagram.
LEGAL_TRANSITIONS: dict[DecisionPhase, frozenset[DecisionPhase]] = {
    DecisionPhase.PREPARING: frozenset({DecisionPhase.READY}),
    DecisionPhase.READY: frozenset({DecisionPhase.REQUEST_PENDING}),
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
    max_protocol_errors: int = Field(ge=1)
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
    max_protocol_errors: int = Field(ge=1)
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
    """Bounded configuration (PRD §38.3 'schema de config').

    ``max_protocol_errors`` is an explicit operational decision (§15.2) with
    no default — callers must choose it. Feature flags are all off by default
    (G-CB-08: reanchoring, parallelism, visual and skills stay disabled until
    ratified and capability-tested).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: COGNITION_CONTRACT_VERSION = 2
    max_rounds: int = Field(ge=1)
    max_protocol_errors: int = Field(ge=1)
    enable_reanchoring: bool = False
    enable_parallelism: bool = False
    enable_visual: bool = False
    enable_skills: bool = False
