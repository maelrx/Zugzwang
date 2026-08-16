"""Event upcasters (design §25.3).

Old events are never rewritten. Readers apply upcasters to produce newer
views; the raw original stays in the bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zugzwang_core.domain.events import EventEnvelope

UpcasterFn = Any


@dataclass(frozen=True, slots=True)
class Upcaster:
    """Maps an old event view to a new one."""

    event_type: str
    from_version: int
    to_version: int
    transform: UpcasterFn


class UpcasterRegistry:
    def __init__(self) -> None:
        self._upcasters: dict[tuple[str, int], Upcaster] = {}

    def register(self, upcaster: Upcaster) -> None:
        key = (upcaster.event_type, upcaster.from_version)
        self._upcasters[key] = upcaster

    def upcast(self, event: EventEnvelope) -> EventEnvelope:
        key = (event.event_type, event.event_version)
        current = event
        while key in self._upcasters:
            upcaster = self._upcasters[key]
            new_payload = upcaster.transform(current.payload)
            current = EventEnvelope(
                schema_version=current.schema_version,
                event_id=current.event_id,
                event_type=current.event_type,
                event_version=upcaster.to_version,
                occurred_at=current.occurred_at,
                stream=current.stream,
                context=current.context,
                payload=new_payload,
                artifact_refs=current.artifact_refs,
                assistance=current.assistance,
            )
            key = (current.event_type, current.event_version)
        return current
