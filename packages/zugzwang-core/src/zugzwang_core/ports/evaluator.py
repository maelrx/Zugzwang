"""Evaluator port (design §16).

Evaluators produce metrics post-hoc and must never alter the trajectory by
default. Every observation carries its definition and provenance; a metric
without them is an orphan number (scientific principle §1).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.artifacts import ArtifactRef
from ..domain.events import JsonValue


class MetricDirection(StrEnum):
    LOWER = "lower_is_better"
    HIGHER = "higher_is_better"
    NONE = "none"


class MetricScope(StrEnum):
    RUN = "run"
    EPISODE = "episode"
    STEP = "step"
    ATTEMPT = "attempt"


class MetricDefinition(BaseModel):
    """A versioned metric formula with complete provenance (design §16.2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    scope: MetricScope
    unit: str
    direction: MetricDirection = MetricDirection.NONE
    requires: tuple[str, ...] = ()
    formula_artifact: ArtifactRef | None = None
    dimensions: tuple[str, ...] = ()
    provenance_source: str = "computed"


class MetricObservation(BaseModel):
    """A measured value tied to a definition and to scope references."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    metric_version: str
    value_num: float | None = None
    value_text: str | None = None
    value_json: dict[str, JsonValue] | None = None
    unit: str = ""
    dimensions: dict[str, JsonValue] = {}
    run_id: str | None = None
    episode_id: str | None = None
    step_id: str | None = None
    attempt_id: str | None = None
    evaluator_id: str
    evaluator_version: str
    provenance_artifact: ArtifactRef | None = None
    observed_at: datetime

    def __post_init__(self) -> None:  # pragma: no cover - pydantic hook
        pass

    @property
    def value(self) -> float | str | dict[str, JsonValue] | None:
        if self.value_num is not None:
            return self.value_num
        if self.value_text is not None:
            return self.value_text
        return self.value_json


class EvaluationContext(BaseModel):
    """Immutable inputs for one evaluation pass: references only, no live state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    episode_id: str | None = None
    evaluator_config: dict[str, JsonValue] = {}
    input_refs: tuple[ArtifactRef, ...] = ()


class EvaluatorResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observations: tuple[MetricObservation, ...]
    plugin_events: tuple[dict[str, JsonValue], ...] = ()


class EvaluatorDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluator_id: str
    evaluator_version: str
    plugin_api: str
    metric_definitions: tuple[MetricDefinition, ...] = ()
    requires_engine: bool = False


@runtime_checkable
class Evaluator(Protocol):
    """Produces MetricObservations. Never mutates run state."""

    @property
    def descriptor(self) -> EvaluatorDescriptor: ...

    async def evaluate(self, context: EvaluationContext) -> EvaluatorResult: ...
