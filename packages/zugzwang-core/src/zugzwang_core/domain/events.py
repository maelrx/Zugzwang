"""Scientific event envelope (design §11.6 and §21.1).

Events are the append-only audit trail. They are not operational logs: payloads
are typed, sequences are monotonic per stream, and heavy content is referenced
as artifacts rather than embedded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .assistance import HClass, KClass
from .clocks import to_iso_z, utc_now
from .ids import Id
from .versions import EVENT_API

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None


class EventStreamRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["experiment", "run", "episode", "step", "attempt"]
    id: str
    sequence: int = Field(ge=0)


class EventContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    condition_id: str | None = None
    episode_id: str | None = None
    step_id: str | None = None
    attempt_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None


class EventAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    h: HClass
    k: KClass = KClass.K0
    source: str = "unspecified"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["zgw.event/v1alpha1"] = EVENT_API
    event_id: str
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]+(\.[a-z][a-z0-9_]+)*$")
    event_version: int = Field(ge=1)
    occurred_at: datetime
    stream: EventStreamRef
    context: EventContext
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()
    assistance: EventAssistance | None = None

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        payload: dict[str, JsonValue],
        stream_type: Literal["experiment", "run", "episode", "step", "attempt"],
        stream_id: str,
        sequence: int,
        context: EventContext,
        artifact_refs: tuple[str, ...] = (),
        assistance: EventAssistance | None = None,
        event_id: Id | None = None,
    ) -> EventEnvelope:
        from .ids import new_id

        return cls(
            event_id=str(event_id if event_id is not None else new_id("evt")),
            event_type=event_type,
            event_version=1,
            occurred_at=utc_now(),
            stream=EventStreamRef(type=stream_type, id=stream_id, sequence=sequence),
            context=context,
            payload=payload,
            artifact_refs=artifact_refs,
            assistance=assistance,
        )

    def to_json_line(self) -> str:
        from .canonical import canonical_json_string

        return canonical_json_string(self.model_dump(mode="json"))


def event_iso(event: EventEnvelope) -> str:
    return to_iso_z(event.occurred_at)
