"""Contract suites shared by every port implementation (ADR-031).

Any ModelBackend must pass this suite (fake now, real adapters in M3);
any Environment and any Evaluator must pass theirs. These are the tests
plugins inherit when they implement a port.
"""

from __future__ import annotations

import pytest

from zugzwang_core.domain.errors import (
    IllegalActionError,
    ProviderResponseError,
    ProviderTransportError,
)
from zugzwang_core.ports.environment import Environment, EpisodeSpec, ObservationPolicy
from zugzwang_core.ports.evaluator import EvaluationContext, Evaluator
from zugzwang_core.ports.model import (
    CallContext,
    Capability,
    Message,
    MessageRole,
    ModelBackend,
    ModelRef,
    ModelRequest,
    OutputConstraint,
    TextPart,
)


async def run_model_backend_contract(backend: ModelBackend) -> None:
    """Full contract suite for a ModelBackend implementation."""

    descriptor = backend.descriptor
    assert descriptor.backend_id, "backend_id required"
    assert descriptor.backend_version, "backend_version required"
    assert descriptor.plugin_api.startswith("zgw.plugin/"), "plugin_api must be versioned"

    model = ModelRef(backend=descriptor.backend_id, provider="contract", model="test")

    report = await backend.inspect_capabilities(
        model,
        required=frozenset({Capability.TEXT_INPUT}),
        preferred=frozenset({Capability.USAGE_REPORTING}),
    )
    assert report.model == model
    assert not report.missing_required or not report.satisfied
    assert isinstance(report.supported, frozenset)

    text_request = ModelRequest(
        model=model,
        messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hello"),)),),
        output_constraint=OutputConstraint(format="text"),
        required_capabilities=frozenset({Capability.TEXT_INPUT}),
    )
    context = CallContext(run_id="run_test", attempt_id="att_test")
    result = await backend.infer(text_request, context)
    response = result.response
    assert response.model_requested == model
    assert response.adapter_version
    assert response.wire_fidelity.value in {"full", "partial", "reconstructed", "unavailable"}
    assert response.usage.input_tokens >= 0 and response.usage.output_tokens >= 0
    assert response.stop_reason.canonical in {
        "end_turn",
        "max_tokens",
        "tool_calls",
        "content_filter",
        "refusal",
        "error",
        "unknown",
    }


async def run_model_backend_failure_contract(backend: ModelBackend) -> None:
    """Failure paths must surface as typed transport/response errors, never silence."""
    model = ModelRef(backend=backend.descriptor.backend_id, provider="contract", model="test")
    request = ModelRequest(
        model=model,
        messages=(Message(role=MessageRole.USER, parts=(TextPart(text="fail"),)),),
    )
    context = CallContext(run_id="run_test", fingerprint="unmatched-marker")
    with pytest.raises((ProviderTransportError, ProviderResponseError)):
        await backend.infer(request, context)


def run_environment_contract(environment: Environment) -> None:
    """Full contract suite for an Environment implementation."""
    descriptor = environment.descriptor
    assert descriptor.environment_id
    assert descriptor.plugin_api.startswith("zgw.plugin/")

    episode = EpisodeSpec(task_type="contract", seed=1, config={"terminal_at": 2, "max_steps": 5})
    state = environment.initial_state(episode)

    observation = environment.observe(state, ObservationPolicy(settings={}))
    assert observation is not None

    legal = environment.legal_actions(state)
    assert len(legal.actions) > 0
    assert legal.legal_hash
    assert legal.ordering_policy and legal.ordering_version
    assert legal.state_fingerprint

    transition = environment.transition(state, legal.actions[0])
    assert transition.action == legal.actions[0]

    snapshot = environment.snapshot(transition.state)
    restored = environment.restore(snapshot)
    assert environment.snapshot(restored).data == snapshot.data


def run_environment_invalid_action_contract(environment: Environment) -> None:
    """The environment rejects illegal actions with IllegalActionError."""
    episode = EpisodeSpec(task_type="contract", seed=2, config={"terminal_at": 5, "max_steps": 5})
    state = environment.initial_state(episode)
    with pytest.raises(IllegalActionError):
        environment.transition(state, "definitely-not-a-legal-action")


async def run_evaluator_contract(evaluator: Evaluator) -> None:
    """Full contract suite for an Evaluator implementation."""
    descriptor = evaluator.descriptor
    assert descriptor.evaluator_id
    assert descriptor.plugin_api.startswith("zgw.plugin/")

    context = EvaluationContext(run_id="run_test", episode_id="ep_test")
    first = await evaluator.evaluate(context)
    second = await evaluator.evaluate(context)
    for observation in first.observations:
        assert observation.metric_id
        assert observation.metric_version
        assert observation.evaluator_id == descriptor.evaluator_id
    assert [o.model_dump(mode="json") for o in first.observations] == [
        o.model_dump(mode="json") for o in second.observations
    ], "evaluator must be idempotent for identical inputs"
