"""CB-WO-02 contract acceptance (PRD §38.3, §7.2, §12.2, §15, §42.6).

Examples from fixtures validate against the strict models and the generated
JSON Schemas; unknown fields are rejected; the §15.1 error catalogue is
exhaustive; only §12.2 transitions are legal; §7.2 key builders are
deterministic with distinct semantics; legacy DecisionContext stays valid.
"""

import json
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from zugzwang_core.domain.cognition import (
    COGNITION_CONTRACT_VERSION,
    DEFAULT_MAX_PROTOCOL_ERRORS,
    INTERNAL_ACTIVE_PHASES,
    LEGAL_TRANSITIONS,
    TOOL_ERROR_CODES,
    CognitiveBoardConfig,
    DecisionManifest,
    DecisionPhase,
    DecisionStatus,
    ToolEnvelope,
    ToolError,
    ToolRequest,
    ToolResult,
    action_id_v2,
    can_transition,
    decision_aggregate,
    state_key_v2,
)
from zugzwang_core.ports.cognition import CognitiveSession, StateIdentityPort
from zugzwang_core.ports.model import ModelRef
from zugzwang_core.ports.strategy import DecisionContext, StrategyDescriptor

pytestmark = pytest.mark.contract

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts" / "cb"
SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _schema_for(target: str) -> dict[str, Any]:
    return json.loads(
        (SCHEMAS / f"{target}.zgw.dev-v1alpha1.schema.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# examples validate against models and generated schemas
# ---------------------------------------------------------------------------


def test_tool_envelope_example_against_model_and_schema() -> None:
    example = _load("tool-envelope-ok.json")
    envelope = ToolEnvelope.model_validate(example)
    assert envelope.request.tool == "board_observe"
    Draft202012Validator(_schema_for("cb-tool-envelope")).validate(example)


def test_decision_manifest_example_against_model_and_schema() -> None:
    example = _load("decision-manifest-ok.json")
    manifest = DecisionManifest.model_validate(example)
    assert manifest.content_sha256 == example["content_sha256"]
    Draft202012Validator(_schema_for("cb-decision-manifest")).validate(example)


def test_config_example_against_model_and_schema() -> None:
    example = _load("config-ok.json")
    config = CognitiveBoardConfig.model_validate(example)
    assert config.enable_reanchoring is False  # G-CB-08 conservative default
    Draft202012Validator(_schema_for("cb-config")).validate(example)


def test_manifest_build_reproduces_fixture_hash() -> None:
    example = _load("decision-manifest-ok.json")
    rebuilt = DecisionManifest.build(**{k: v for k, v in example.items() if k != "content_sha256"})
    assert rebuilt == DecisionManifest.model_validate(example)


# ---------------------------------------------------------------------------
# unknown-field rejection (extra=forbid)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "example_fixture", "bad_field"),
    [
        (ToolRequest, "tool-envelope-ok.json", "request"),
        (ToolResult, "tool-envelope-ok.json", "result"),
        (DecisionManifest, "decision-manifest-ok.json", None),
        (CognitiveBoardConfig, "config-ok.json", None),
    ],
)
def test_unknown_fields_are_rejected(
    model: type[BaseModel], example_fixture: str, bad_field: str | None, tmp_path: Path
) -> None:
    example = json.loads((FIXTURES / example_fixture).read_text(encoding="utf-8"))
    target = example[bad_field] if bad_field else example
    target["totally_unknown_field"] = 1
    with pytest.raises(ValidationError):
        model.model_validate(target)


def test_unknown_tool_error_code_is_rejected() -> None:
    with pytest.raises(ValueError):
        ToolError.build("NOT_IN_CATALOGUE", "nope")


# ---------------------------------------------------------------------------
# §15.1/§15.2 — exhaustive error catalogue
# ---------------------------------------------------------------------------


def test_error_catalogue_covers_all_sixteen_codes() -> None:
    expected = {
        "INVALID_ARGUMENTS",
        "TOOL_NOT_ALLOWED",
        "CAPABILITY_DENIED",
        "NODE_SCOPE_MISMATCH",
        "ACTION_STATE_MISMATCH",
        "ILLEGAL_ACTION",
        "TERMINAL_NODE",
        "DEPTH_LIMIT",
        "BUDGET_INSUFFICIENT",
        "CONTEXT_LIMIT",
        "SOURCE_NOT_ALLOWED",
        "STATE_REPLAY_MISMATCH",
        "SEMANTICS_MISMATCH",
        "PROVIDER_OUTCOME_UNKNOWN",
        "PERSISTENCE_FAILED",
        "OUTPUT_CONTRACT_VIOLATION",
    }
    assert expected == TOOL_ERROR_CODES
    for code in expected:
        error = ToolError.build(code, f"diagnostic for {code}")
        assert error.category.value
        assert error.retry_class.value


def test_transport_unknown_outcome_is_pause_or_explicit_retry() -> None:
    error = ToolError.build("PROVIDER_OUTCOME_UNKNOWN", "timeout, result unknown")
    assert error.retry_class.value == "pause_or_explicit_retry"


def test_max_protocol_errors_conservative_default() -> None:
    assert DEFAULT_MAX_PROTOCOL_ERRORS >= 1
    assert CognitiveBoardConfig().max_protocol_errors == DEFAULT_MAX_PROTOCOL_ERRORS


# ---------------------------------------------------------------------------
# §12.2 — state machine
# ---------------------------------------------------------------------------


def test_happy_path_transitions_are_legal() -> None:
    path = [
        DecisionPhase.PREPARING,
        DecisionPhase.READY,
        DecisionPhase.REQUEST_PENDING,
        DecisionPhase.RESPONSE_COMMITTED,
        DecisionPhase.TOOL_EXECUTING,
        DecisionPhase.ROUND_COMMITTED,
        DecisionPhase.READY,
        DecisionPhase.REQUEST_PENDING,
        DecisionPhase.RESPONSE_COMMITTED,
        DecisionPhase.FINALIZING,
        DecisionPhase.SELECTED,
        DecisionPhase.COMMITTED,
    ]
    for current, target in pairwise(path):
        assert can_transition(current, target), f"{current} -> {target}"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DecisionPhase.PREPARING, DecisionPhase.SELECTED),
        (DecisionPhase.READY, DecisionPhase.COMMITTED),
        (DecisionPhase.REQUEST_PENDING, DecisionPhase.SELECTED),
        (DecisionPhase.PAUSED, DecisionPhase.READY),
        (DecisionPhase.COMMITTED, DecisionPhase.READY),
        (DecisionPhase.OUTCOME_UNKNOWN, DecisionPhase.SELECTED),
        (DecisionPhase.FAILED, DecisionPhase.READY),
    ],
)
def test_illegal_transitions_are_rejected(current: DecisionPhase, target: DecisionPhase) -> None:
    assert not can_transition(current, target)


def test_terminal_and_paused_states_have_no_outgoing_transitions() -> None:
    assert LEGAL_TRANSITIONS[DecisionPhase.PAUSED] == frozenset()
    assert LEGAL_TRANSITIONS[DecisionPhase.COMMITTED] == frozenset()
    assert LEGAL_TRANSITIONS[DecisionPhase.FAILED] == frozenset()
    assert LEGAL_TRANSITIONS[DecisionPhase.CANCELLED] == frozenset()


def test_internal_phases_map_to_active_aggregate() -> None:
    for phase in DecisionPhase:
        aggregate = decision_aggregate(phase)
        if phase in INTERNAL_ACTIVE_PHASES:
            assert aggregate is DecisionStatus.ACTIVE
        else:
            assert aggregate is DecisionStatus(phase.value)


# ---------------------------------------------------------------------------
# §7.2 — deterministic identity keys with distinct semantics
# ---------------------------------------------------------------------------


def test_identity_keys_are_deterministic_and_versioned() -> None:
    k1 = state_key_v2("fen-a", "standard", "rules-ctx")
    k2 = state_key_v2("fen-a", "standard", "rules-ctx")
    assert k1 == k2
    assert k1.startswith("state_key:v2:")
    assert state_key_v2("fen-b", "standard", "rules-ctx") != k1
    assert state_key_v2("fen-a", "chess960", "rules-ctx") != k1


def test_action_key_binds_state_uci_and_policy() -> None:
    state = state_key_v2("fen-a", "standard", "rules-ctx")
    other = state_key_v2("fen-b", "standard", "rules-ctx")
    assert action_id_v2(state, "e2e4", "v1", "policy-aaa") != action_id_v2(
        state, "e2e4", "v1", "policy-bbb"
    )
    assert action_id_v2(state, "e2e4", "v1", "policy-aaa") != action_id_v2(
        other, "e2e4", "v1", "policy-aaa"
    )


# ---------------------------------------------------------------------------
# §26.1 — additive DecisionContext compatibility
# ---------------------------------------------------------------------------


def _legacy_context_kwargs() -> dict[str, Any]:
    """Minimal valid context shaped like pre-CognitiveBoard call sites."""
    return {
        "run_id": "run-1",
        "episode_id": "ep-1",
        "step_id": "st-1",
        "model": ModelRef(backend="fake", provider="fake", model="fake-model"),
        "backend": None,
        "tools": {},
        "seed": 1,
    }


def test_legacy_decision_context_without_session_still_valid() -> None:
    context = DecisionContext(**_legacy_context_kwargs())
    assert context.decision_session is None


def test_decision_context_accepts_optional_session() -> None:
    context = DecisionContext(**_legacy_context_kwargs(), decision_session=object())
    assert context.decision_session is not None


def test_legacy_strategy_descriptor_still_valid() -> None:
    descriptor = StrategyDescriptor.model_validate(
        {
            "strategy_id": "chess.grounded",
            "strategy_version": "0.1.0",
            "plugin_api": "zgw.plugin/v1alpha1",
            "declared_regime": "R1",
            "declared_assistance_h": "H1",
            "declared_assistance_k": "K0",
        }
    )
    assert descriptor.declared_regime == "R1"


def test_identity_and_session_protocols_are_runtime_checkable() -> None:
    assert StateIdentityPort and CognitiveSession


# contract version is pinned
def test_contract_version_is_two() -> None:
    assert CognitiveBoardConfig().contract_version == 2
    assert Literal[2] == COGNITION_CONTRACT_VERSION
