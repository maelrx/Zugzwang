"""Typed tool contract (design §13.5).

Tools carry governance metadata: determinism, side effects, network/filesystem
scope, assistance impact and trust level. Discovery never implies
authorization; the runtime enforces the allowlist (design §13.8).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.assistance import AssistanceImpact
from ..domain.events import JsonValue


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str
    input_schema: dict[str, JsonValue] = {}
    output_schema: dict[str, JsonValue] = {}
    deterministic: bool = True
    side_effects: tuple[str, ...] = ()
    network_scope: str = "none"
    filesystem_scope: str = "none"
    timeout_seconds: float | None = None
    assistance_impact: AssistanceImpact
    source_of_truth: str
    cache_policy: str = "none"
    trust_level: str = "first_party"


class ToolContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    episode_id: str
    step_id: str
    config: dict[str, JsonValue] = {}


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data: dict[str, JsonValue] = {}
    assistance_impact: AssistanceImpact | None = None
    plugin_events: tuple[dict[str, JsonValue], ...] = ()


@runtime_checkable
class Tool(Protocol):
    @property
    def descriptor(self) -> ToolDescriptor: ...

    async def invoke(
        self,
        arguments: dict[str, JsonValue],
        context: ToolContext,
    ) -> ToolResult: ...
