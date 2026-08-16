"""Plugin descriptor contract (design §19.3).

Plugins are discovered through PyPA entry-point groups and declared through
descriptors. The registry rejects incompatible plugin_api versions and never
tries to adapt magically (design §19.4).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..domain.events import JsonValue
from ..domain.versions import PLUGIN_API

PROVIDER_GROUP = "zugzwang.providers"
ENVIRONMENT_GROUP = "zugzwang.environments"
TASK_GROUP = "zugzwang.tasks"
STRATEGY_GROUP = "zugzwang.strategies"
POLICY_GROUP = "zugzwang.policies"
VERIFIER_GROUP = "zugzwang.verifiers"
EVALUATOR_GROUP = "zugzwang.evaluators"
REPORTER_GROUP = "zugzwang.reporters"
CODEC_GROUP = "zugzwang.codecs"

ALL_GROUPS: tuple[str, ...] = (
    PROVIDER_GROUP,
    ENVIRONMENT_GROUP,
    TASK_GROUP,
    STRATEGY_GROUP,
    POLICY_GROUP,
    VERIFIER_GROUP,
    EVALUATOR_GROUP,
    REPORTER_GROUP,
    CODEC_GROUP,
)


class PluginKind(StrEnum):
    PROVIDER = "provider"
    ENVIRONMENT = "environment"
    TASK = "task"
    STRATEGY = "strategy"
    POLICY = "policy"
    VERIFIER = "verifier"
    EVALUATOR = "evaluator"
    REPORTER = "reporter"
    CODEC = "codec"


class TrustLevel(StrEnum):
    FIRST_PARTY = "first_party"
    THIRD_PARTY = "third_party"


class IsolationMode(StrEnum):
    IN_PROCESS = "in_process"
    SUBPROCESS = "subprocess"


class PluginDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")
    plugin_version: str
    plugin_api: str = PLUGIN_API
    kind: PluginKind
    config_schema: dict[str, JsonValue] | None = None
    capabilities: tuple[str, ...] = ()
    license: str
    trust: TrustLevel = TrustLevel.FIRST_PARTY
    isolation: IsolationMode = IsolationMode.IN_PROCESS


@runtime_checkable
class PluginDefinition(Protocol):
    """What an entry point must expose to be discoverable."""

    @property
    def descriptor(self) -> PluginDescriptor: ...
