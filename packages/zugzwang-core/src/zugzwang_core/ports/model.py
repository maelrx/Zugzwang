"""Canonical provider contract (design §12).

The contract represents ONE inference call — not an agent loop. Frameworks and
SDKs are replaceable adapters behind these types.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.artifacts import ArtifactRef
from ..domain.events import JsonValue
from ..domain.money import CostEntry, TokenUsage
from ..domain.versions import MODEL_REQUEST_API


class Capability(StrEnum):
    TEXT_INPUT = "text_input"
    JSON_SCHEMA_OUTPUT = "json_schema_output"
    TOOL_CALLING = "tool_calling"
    PARALLEL_TOOL_CALLS = "parallel_tool_calls"
    STREAMING = "streaming"
    SEED = "seed"
    REASONING_CONTROL = "reasoning_control"
    PROMPT_CACHING = "prompt_caching"
    USAGE_REPORTING = "usage_reporting"
    COST_REPORTING = "cost_reporting"
    LOGPROBS = "logprobs"
    MULTIMODAL_IMAGE = "multimodal_image"
    BATCH = "batch"
    IDEMPOTENCY_KEY = "idempotency_key"


class OnUnsupported(StrEnum):
    FAIL = "fail"
    EMULATE = "emulate"
    DEGRADE = "degrade"


class WireFidelity(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    RECONSTRUCTED = "reconstructed"
    UNAVAILABLE = "unavailable"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TextPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["text"] = "text"
    text: str


class JsonDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["json_data"] = "json_data"
    data: dict[str, JsonValue]


class ToolCallPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: dict[str, JsonValue]


class ToolResultPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False


class StatusPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["status"] = "status"
    kind: Literal["refusal", "error"]
    message: str


MessagePart = TextPart | JsonDataPart | ToolCallPart | ToolResultPart | StatusPart


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: MessageRole
    parts: tuple[MessagePart, ...]


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class OutputConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    format: Literal["text", "json_schema", "json_object"]
    schema_: dict[str, JsonValue] | None = Field(default=None, alias="schema")

    def model_dump_with_alias(self) -> dict[str, JsonValue]:
        return dict(self.model_dump(mode="json", by_alias=True))


class InferenceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    temperature: float | None = Field(default=None, ge=0.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    seed: int | None = None
    stop: tuple[str, ...] = ()
    extensions: dict[str, JsonValue] = Field(default_factory=dict)


class ModelRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    backend: str
    provider: str
    model: str

    def __str__(self) -> str:
        return f"{self.backend}/{self.provider}/{self.model}"


class ModelRequest(BaseModel):
    """Canonical request. Frozen; extensions are namespaced, not lowest-common."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["zgw.model-request/v1alpha1"] = MODEL_REQUEST_API
    model: ModelRef
    messages: tuple[Message, ...]
    tools: tuple[ToolDefinition, ...] = ()
    output_constraint: OutputConstraint = OutputConstraint(format="text")
    inference: InferenceSettings = InferenceSettings()
    required_capabilities: frozenset[Capability] = frozenset()
    preferred_capabilities: frozenset[Capability] = frozenset()
    extensions: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class StopReason(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    canonical: Literal[
        "end_turn",
        "max_tokens",
        "tool_calls",
        "content_filter",
        "refusal",
        "error",
        "unknown",
    ]
    raw: str | None = None


class NormalizedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["zgw.model-request/v1alpha1"] = MODEL_REQUEST_API
    content_parts: tuple[MessagePart, ...] = ()
    tool_calls: tuple[ToolCallPart, ...] = ()
    stop_reason: StopReason = StopReason(canonical="unknown")
    model_requested: ModelRef
    model_reported: str | None = None
    request_id: str | None = None
    usage: TokenUsage = TokenUsage()
    cost: CostEntry | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    raw_response: ArtifactRef | None = None
    adapter_version: str
    wire_fidelity: WireFidelity = WireFidelity.FULL
    warnings: tuple[str, ...] = ()

    def text(self) -> str:
        return "".join(p.text for p in self.content_parts if isinstance(p, TextPart))


class CallContext(BaseModel):
    """Operational context for one inference call (never contains secrets)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    episode_id: str | None = None
    step_id: str | None = None
    attempt_id: str | None = None
    trace_id: str | None = None
    fingerprint: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class BackendDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    backend_version: str
    plugin_api: str
    default_capabilities: frozenset[Capability] = frozenset()
    known_models: tuple[ModelRef, ...] = ()
    limitations: tuple[str, ...] = ()


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: ModelRef
    supported: frozenset[Capability]
    missing_required: frozenset[Capability]
    missing_preferred: frozenset[Capability]
    on_unsupported: OnUnsupported = OnUnsupported.FAIL
    warnings: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        return not self.missing_required


class ProviderResult(BaseModel):
    """Result of one infer call plus plugin-emitted events (design §32.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    response: NormalizedResponse
    plugin_events: tuple[dict[str, JsonValue], ...] = ()


@runtime_checkable
class ModelBackend(Protocol):
    """One inference port. Never an agent, policy or player."""

    @property
    def descriptor(self) -> BackendDescriptor: ...

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport: ...

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult: ...
