"""CounterEnvironment: a trivial domain proving the core needs no chess.

State is an integer counter; legal actions are ``inc`` and ``dec``; the
episode terminates when the counter reaches ``terminal_at`` or after
``max_steps`` transitions. Invalid actions are rejected here — the
environment is the only authority (NFR-001).
"""

from __future__ import annotations

from dataclasses import dataclass

from zugzwang_core.domain.artifacts import ArtifactPayload
from zugzwang_core.domain.errors import EnvironmentError_, IllegalActionError
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.environment import (
    EnvironmentDescriptor,
    EpisodeSpec,
    LegalActionSet,
    ObservationPolicy,
    Termination,
    Transition,
)

_COUNTER_SNAPSHOT_MEDIA_TYPE = "application/x-zugzwang-counter-state+json"


def _as_int(value: JsonValue | None) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise EnvironmentError_(f"counter config value must be numeric, got {value!r}")
    return int(value)


@dataclass(frozen=True, slots=True)
class CounterState:
    count: int
    steps_taken: int
    terminal_at: int
    max_steps: int

    @property
    def terminal(self) -> bool:
        return self.count >= self.terminal_at or self.steps_taken >= self.max_steps


class CounterEnvironment:
    environment_id = "fake.environment"
    environment_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    @property
    def descriptor(self) -> EnvironmentDescriptor:
        return EnvironmentDescriptor(
            environment_id=self.environment_id,
            environment_version=self.environment_version,
            plugin_api=self.plugin_api,
            state_type="counter",
            action_type="str",
        )

    def initial_state(self, episode: EpisodeSpec) -> CounterState:
        config = episode.config
        start = _as_int(config.get("start", 0))
        terminal_at = _as_int(config.get("terminal_at", 3))
        max_steps = _as_int(config.get("max_steps", 10))
        return CounterState(
            count=start, steps_taken=0, terminal_at=terminal_at, max_steps=max_steps
        )

    def observe(self, state: CounterState, policy: ObservationPolicy) -> dict[str, JsonValue]:
        settings = policy.settings
        representation = settings.get("representation", "text")
        payload: dict[str, JsonValue] = {
            "count": state.count,
            "steps_taken": state.steps_taken,
            "remaining": max(state.terminal_at - state.count, 0),
        }
        if settings.get("legal_actions", False):
            payload["legal_actions"] = ["inc", "dec"]
        if representation == "text":
            return {"text": f"counter={state.count} steps={state.steps_taken}"}
        return payload

    def legal_actions(
        self, state: CounterState, *, encoding: str = "canonical"
    ) -> LegalActionSet[str]:
        actions = ("inc", "dec")
        if state.count <= 0:
            actions = ("inc",)
        import hashlib

        from zugzwang_core.domain.canonical import hash_canonical

        legal_hash = hash_canonical({"actions": list(actions), "state": state.count})
        fingerprint = hashlib.sha256(
            f"counter:{state.count}:{state.steps_taken}".encode()
        ).hexdigest()
        return LegalActionSet(
            actions=actions,
            ordering_policy="fixed",
            ordering_version="1",
            encoding=encoding,
            legal_hash=legal_hash,
            state_fingerprint=fingerprint,
        )

    def transition(self, state: CounterState, action: str) -> Transition[CounterState, str]:
        legal = self.legal_actions(state)
        if action not in legal.actions:
            raise IllegalActionError(
                f"illegal action {action!r}",
                technical_context=f"legal={list(legal.actions)}",
            )
        next_count = state.count + (1 if action == "inc" else -1)
        next_state = CounterState(
            count=next_count,
            steps_taken=state.steps_taken + 1,
            terminal_at=state.terminal_at,
            max_steps=state.max_steps,
        )
        if next_state.terminal:
            return Transition(
                state=next_state,
                action=action,
                terminal=True,
                termination=Termination(kind="counter_reached", result="success"),
            )
        return Transition(state=next_state, action=action)

    def snapshot(self, state: CounterState) -> ArtifactPayload:
        from zugzwang_core.domain.canonical import canonical_json_string

        data = canonical_json_string(
            {
                "count": state.count,
                "steps_taken": state.steps_taken,
                "terminal_at": state.terminal_at,
                "max_steps": state.max_steps,
            }
        ).encode("utf-8")
        return ArtifactPayload(media_type=_COUNTER_SNAPSHOT_MEDIA_TYPE, data=data)

    def restore(self, snapshot: ArtifactPayload) -> CounterState:
        import json

        if snapshot.media_type != _COUNTER_SNAPSHOT_MEDIA_TYPE:
            raise EnvironmentError_(f"cannot restore counter state from {snapshot.media_type}")
        data = json.loads(snapshot.data.decode("utf-8"))
        return CounterState(
            count=int(data["count"]),
            steps_taken=int(data["steps_taken"]),
            terminal_at=int(data["terminal_at"]),
            max_steps=int(data["max_steps"]),
        )


class FakeEnvironmentDefinition:
    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="fake.environment",
            plugin_version="0.1.0",
            kind=PluginKind.ENVIRONMENT,
            capabilities=("snapshot", "restore"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )
