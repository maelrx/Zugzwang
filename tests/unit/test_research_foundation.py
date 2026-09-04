"""Contracts for the evidence and formal-assistance firewall."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


@pytest.mark.unit
def test_provider_result_can_retain_wire_and_reasoning_telemetry() -> None:
    from zugzwang_core.ports.model import (
        ModelRef,
        NormalizedResponse,
        ProviderResult,
        ReasoningTelemetry,
        WireFidelity,
    )

    model = ModelRef(backend="provider.mock", provider="mock", model="m")
    response = NormalizedResponse(model_requested=model, adapter_version="test")
    result = ProviderResult(
        response=response,
        wire_request={"model": "m", "input": [{"role": "user"}]},
        wire_response={"id": "resp_1", "status": "completed"},
        reasoning_telemetry=ReasoningTelemetry(
            provider="mock",
            model="m",
            reasoning_effort="minimal",
            reasoning_summary="provider-exposed summary",
            availability={
                "reasoning_tokens": True,
                "reasoning_items": True,
                "reasoning_summary": True,
            },
            usage={"output_tokens": 12, "reasoning_tokens": 7},
        ),
        wire_fidelity=WireFidelity.FULL,
    )

    assert result.wire_request is not None
    assert result.wire_response == {"id": "resp_1", "status": "completed"}
    assert result.reasoning_telemetry is not None
    assert result.reasoning_telemetry.reasoning_summary == "provider-exposed summary"


@pytest.mark.unit
def test_reasoning_telemetry_never_fabricates_unavailable_fields() -> None:
    from zugzwang_core.ports.model import ReasoningTelemetry

    telemetry = ReasoningTelemetry(
        provider="opencode-go",
        model="muse-spark-1.3",
        availability={
            "reasoning_tokens": False,
            "reasoning_items": False,
            "reasoning_summary": False,
        },
    )

    assert telemetry.reasoning_tokens is None
    assert telemetry.reasoning_items == ()
    assert telemetry.reasoning_summary is None


@pytest.mark.unit
def test_binary_legality_policy_disallows_enumeration() -> None:
    from zugzwang_core.ports.rules import LegalityGatewayConfig

    config = LegalityGatewayConfig.model_validate(
        {
            "validation": {"enabled": True, "feedback": "binary"},
            "enumerate": {"enabled": False},
        }
    )
    assert config.validation_feedback == "binary"
    assert not config.enumerate_enabled


@pytest.mark.unit
def test_manifest_has_explicit_retry_profiles() -> None:
    from zugzwang_core.domain.manifests import SourceManifest

    data = {
        "api_version": "zgw.dev/v1alpha1",
        "kind": "Experiment",
        "metadata": {"name": "retry-profile-test"},
        "spec": {
            "seed": 1,
            "task": {"plugin": "fake.counter"},
            "players": {
                "white": {
                    "model": {
                        "backend": "fake.backend",
                        "provider": "fake",
                        "model": "scripted",
                        "strategy": "fake.direct",
                    }
                },
                "black": {"policy": {"plugin": "fake.stay"}},
            },
            "protocol": {
                "declared_assistance": "H2",
                "retry_profile": "binary_legality",
                "legality": {
                    "validation": {"enabled": True, "feedback": "binary"},
                    "enumerate": {"enabled": False},
                },
            },
        },
    }

    manifest = SourceManifest.model_validate(data)
    assert manifest.spec.protocol.retry_profile == "binary_legality"
    assert manifest.spec.protocol.legality.enumerate.enabled is False


@pytest.mark.unit
def test_rules_kernel_protocol_is_runtime_checkable_contract() -> None:
    from zugzwang_core.ports.rules import LegalityResult, ParseResult

    assert ParseResult(parsed=None, valid=False, error="bad").valid is False
    with pytest.raises(ValidationError):
        LegalityResult(legal="yes")


@pytest.mark.unit
def test_delayed_legal_actions_are_not_materialized_before_gateway_lease() -> None:
    from zugzwang_chess.environment.standard import (
        ChessGameState,
        StandardChessEnvironment,
        StandardChessRulesKernel,
    )
    from zugzwang_core.domain.errors import CapabilityError
    from zugzwang_core.ports.environment import ObservationPolicy
    from zugzwang_core.ports.rules import DecisionCapabilities, LegalityGatewayConfig
    from zugzwang_runtime.execution.legality import LegalityGateway

    environment = StandardChessEnvironment()
    state = ChessGameState()
    observation = environment.observe(
        state,
        ObservationPolicy(
            settings={
                "position": {"fen": True},
                "legal_actions": {"exposure": "delayed", "encoding": "uci"},
            }
        ),
    )
    assert "legal_actions" not in observation

    gateway = LegalityGateway(
        StandardChessRulesKernel(environment),
        LegalityGatewayConfig(
            validation={"enabled": True, "feedback": "binary"},
            enumerate={"enabled": False},
        ),
    )
    bound = gateway.bind(
        state=state,
        capabilities=DecisionCapabilities(
            validate_action=True,
            validation_feedback="binary",
        ),
    )
    result = bound.validate(type("Move", (), {"uci": "e2e5"})())
    assert bound.model_feedback(result) == {"legal": False}
    assert "legal_moves" not in bound.model_feedback(result)
    with pytest.raises(CapabilityError):
        bound.enumerate_actions()
