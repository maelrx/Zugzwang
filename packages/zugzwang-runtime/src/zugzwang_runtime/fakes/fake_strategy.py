"""FakeDirectStrategy (R0): one observation, one inference, one parse.

Baseline strategy: builds a single message from the observation, calls the
backend once, parses the text response as the action, and returns a complete
DecisionTrace. No hidden retries, no fallback.
"""

from __future__ import annotations

from typing import Any, cast

from zugzwang_core.domain.assistance import AssistanceImpact, HClass
from zugzwang_core.domain.errors import ProviderTransportError
from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRequest,
    OutputConstraint,
    TextPart,
)
from zugzwang_core.ports.strategy import (
    CallRecord,
    Candidate,
    DecisionContext,
    DecisionTrace,
    StrategyDescriptor,
    Verdict,
)


class FakeDirectStrategy:
    strategy_id = "fake.direct"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, max_model_calls: int = 1) -> None:
        self._max_model_calls = max_model_calls

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R0",
            declared_assistance_h="H2",
            declared_assistance_k="K0",
            consumes_legal_actions=False,
            produces_candidates=False,
            max_model_calls=self._max_model_calls,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        text = self._observation_text(observation)
        message = Message(role=MessageRole.USER, parts=(TextPart(text=text),))
        request = ModelRequest(
            model=context.model,
            messages=(message,),
            output_constraint=OutputConstraint(format="text"),
            extensions={"fake.strategy": "direct"},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"fake-direct:{text}",
        )
        try:
            result = await context.backend.infer(request, call_context)
        except ProviderTransportError as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R0",
                calls=(),
                verdicts=(Verdict(kind="provider_error", message=exc.stable_code),),
                final_action=None,
                termination_reason="provider_error",
            )
        response = result.response
        action_text = response.text().strip()
        if not action_text:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R0",
                calls=(self._call_record(response, attempt_id="att-placeholder"),),
                verdicts=(Verdict(kind="parse_error", message="empty response"),),
                final_action=None,
                termination_reason="parse_error",
            )
        impact = AssistanceImpact(h=HClass.H0, source="formal_parser")
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R0",
            calls=(
                self._call_record(
                    response, attempt_id=call_context.attempt_id or "att-placeholder"
                ),
            ),
            candidates=(Candidate(action=action_text, origin="model_output"),),
            verdicts=(Verdict(kind="parse_ok", message="action parsed", assistance_impact=impact),),
            final_action=action_text,
            termination_reason="selected",
            assistance_impacts=(impact,),
        )

    @staticmethod
    def _observation_text(observation: Any) -> str:
        if isinstance(observation, dict):
            raw: dict[Any, Any] = cast(dict[Any, Any], observation)
            text_value = raw.get("text")
            if text_value is not None:
                return str(text_value)
        return str(cast(object, observation))

    @staticmethod
    def _call_record(response: Any, attempt_id: str) -> CallRecord:
        return CallRecord(
            attempt_id=attempt_id,
            response_ok=True,
            usage=response.usage,
            cost=None,
            latency_ms=None,
        )


class FakeStrategyDefinition:
    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="fake.direct",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R0",),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )
