"""Decision strategy port (design §13).

A DecisionStrategy coordinates calls, tools, semantic retries and selection —
explicitly, with a full DecisionTrace. No external framework decides silently
when to stop, retry or switch models.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.assistance import AssistanceImpact
from ..domain.events import JsonValue
from ..domain.money import CostEntry, TokenUsage
from .model import ModelRef
from .rules import DecisionCapabilities


class StrategyDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    strategy_version: str
    plugin_api: str
    declared_regime: str = Field(pattern=r"^R[0-9]+$")
    declared_assistance_h: str = Field(pattern=r"^H[0-7]$")
    declared_assistance_k: str = Field(pattern=r"^K[0-7]$")
    consumes_legal_actions: bool = False
    produces_candidates: bool = False
    max_model_calls: int = 1


class DecisionContext(BaseModel):
    """Everything a strategy may use during one step decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    episode_id: str
    step_id: str
    model: ModelRef
    backend: Any
    tools: dict[str, Any]
    seed: int
    config: dict[str, JsonValue] = {}
    artifact_store: Any = None
    knowledge: tuple[Any, ...] = ()
    # These are scoped per decision phase.  They are intentionally opaque to
    # the core contract so the runtime can bind a concrete gateway/workspace
    # without importing chess or a provider here.
    state: Any = None
    capabilities: DecisionCapabilities = DecisionCapabilities()
    legality_gateway: Any = None
    search_workspace: Any = None
    search_memory: Any = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Any
    origin: str
    evidence_artifact_refs: tuple[str, ...] = ()
    score: float | None = None
    self_estimate: dict[str, JsonValue] = {}


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    message: str = ""
    assistance_impact: AssistanceImpact | None = None


class CallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: str
    request_fingerprint: str | None = None
    response_ok: bool
    usage: TokenUsage
    cost: CostEntry | None = None
    latency_ms: int | None = None
    request_artifact_ref: str | None = None
    response_artifact_ref: str | None = None
    failure_code: str | None = None


class DecisionTrace(BaseModel):
    """Complete, auditable trace of one decision (design §13.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    strategy_version: str
    declared_regime: str
    calls: tuple[CallRecord, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    tool_invocations: tuple[str, ...] = ()
    verdicts: tuple[Verdict, ...] = ()
    selection_rationale: dict[str, JsonValue] | None = None
    final_action: Any | None = None
    termination_reason: str = "selected"
    assistance_impacts: tuple[AssistanceImpact, ...] = ()
    artifact_refs: tuple[str, ...] = ()


class ObservationArtifact(BaseModel):
    """Exact model-facing observation stored as a versioned CAS payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "zgw.observation/v1"
    run_id: str
    episode_id: str
    step_id: str
    state_ref: str
    state_fingerprint: str | None = None
    sources: dict[str, JsonValue]
    policy: dict[str, JsonValue]
    payload: dict[str, JsonValue]
    assistance: dict[str, JsonValue]


class DecisionTraceArtifact(BaseModel):
    """Durable form of one strategy decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "zgw.decision-trace/v1"
    run_id: str
    episode_id: str
    step_id: str
    strategy: dict[str, JsonValue]
    calls: tuple[CallRecord, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    tool_invocations: tuple[str, ...] = ()
    verdicts: tuple[Verdict, ...] = ()
    selection_rationale: dict[str, JsonValue] | None = None
    final_action: Any | None = None
    termination_reason: str = "selected"
    assistance_impacts: tuple[AssistanceImpact, ...] = ()
    artifact_refs: tuple[str, ...] = ()


@runtime_checkable
class DecisionStrategy(Protocol):
    """Transforms an observation into a DecisionTrace via explicit stages."""

    @property
    def descriptor(self) -> StrategyDescriptor: ...

    async def decide(
        self,
        observation: Any,
        context: DecisionContext,
    ) -> DecisionTrace: ...
