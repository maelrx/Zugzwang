"""FakeEvaluator: deterministic, idempotent, provenance-carrying metrics."""

from __future__ import annotations

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.ports.evaluator import (
    EvaluationContext,
    EvaluatorDescriptor,
    EvaluatorResult,
    MetricDefinition,
    MetricDirection,
    MetricObservation,
    MetricScope,
)

from ..coercions import as_float


class FakeEvaluator:
    evaluator_id = "fake.evaluator"
    evaluator_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    @property
    def descriptor(self) -> EvaluatorDescriptor:
        return EvaluatorDescriptor(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            plugin_api=self.plugin_api,
            metric_definitions=(
                MetricDefinition(
                    metric_id="fake.final_count",
                    version="1.0.0",
                    scope=MetricScope.EPISODE,
                    unit="count",
                    direction=MetricDirection.NONE,
                    provenance_source="computed",
                ),
            ),
            requires_engine=False,
        )

    async def evaluate(self, context: EvaluationContext) -> EvaluatorResult:
        final_count = context.evaluator_config.get("final_count")
        observations: tuple[MetricObservation, ...] = ()
        if final_count is not None:
            observations = (
                MetricObservation(
                    metric_id="fake.final_count",
                    metric_version="1.0.0",
                    value_num=as_float(final_count, 0.0),
                    unit="count",
                    run_id=context.run_id,
                    episode_id=context.episode_id,
                    evaluator_id=self.evaluator_id,
                    evaluator_version=self.evaluator_version,
                    observed_at=utc_now(),
                ),
            )
        return EvaluatorResult(observations=observations)


class FakeEvaluatorDefinition:
    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="fake.evaluator",
            plugin_version="0.1.0",
            kind=PluginKind.EVALUATOR,
            capabilities=("fake.final_count",),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )
