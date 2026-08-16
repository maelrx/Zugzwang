"""Environment port (design §32.2 and §4.3).

The environment is the sole authority for state, legality, transition and
termination. Models and tools never mutate canonical state directly
(NFR-001, FR-014).
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

from ..domain.artifacts import ArtifactPayload
from ..domain.events import JsonValue

StateT = TypeVar("StateT")
ActionT = TypeVar("ActionT")
ObservationT = TypeVar("ObservationT", covariant=True)


class EnvironmentDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment_id: str
    environment_version: str
    plugin_api: str
    state_type: str
    action_type: str
    supports_snapshot: bool = True


class EpisodeSpec(BaseModel):
    """Task-derived spec used to build an initial state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_type: str
    seed: int
    config: dict[str, JsonValue] = {}


class ObservationPolicy(BaseModel):
    """Which representations are delivered to the policy (design §14.4).

    Each representation produces its own fingerprint: the same state with FEN
    and ASCII constitutes a different experimental interface.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings: dict[str, JsonValue] = {}

    def fingerprint(self) -> str:
        from ..domain.canonical import hash_canonical

        return hash_canonical(self.settings)


class LegalActionSet[ActionT](BaseModel):
    """Legal actions with stable ordering and reproducibility metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actions: tuple[Any, ...]
    ordering_policy: str
    ordering_version: str
    encoding: str
    legal_hash: str
    leakage_annotations: tuple[str, ...] = ()
    source: str = "rules_engine"
    state_fingerprint: str = ""


class Termination(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    result: str | None = None
    reason: str = ""
    details: dict[str, JsonValue] = {}


class Transition[StateT, ActionT](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: StateT
    action: ActionT | None = None
    terminal: bool = False
    termination: Termination | None = None
    warnings: tuple[str, ...] = ()


@runtime_checkable
class Environment(Protocol[StateT, ActionT, ObservationT]):
    """Authority over state, legality, transition and termination."""

    @property
    def descriptor(self) -> EnvironmentDescriptor: ...

    def initial_state(self, episode: EpisodeSpec) -> StateT: ...

    def observe(self, state: StateT, policy: ObservationPolicy) -> ObservationT: ...

    def legal_actions(
        self, state: StateT, *, encoding: str = "canonical"
    ) -> LegalActionSet[ActionT]: ...

    def transition(self, state: StateT, action: ActionT) -> Transition[StateT, ActionT]: ...

    def snapshot(self, state: StateT) -> ArtifactPayload: ...

    def restore(self, snapshot: ArtifactPayload) -> StateT: ...
