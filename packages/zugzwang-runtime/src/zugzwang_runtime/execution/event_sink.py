"""Event sinks.

The scientific event stream is append-only with monotonic sequences per
stream. M0 uses an in-memory sink; M1 replaces it with the single-writer
PersistenceWriter over SQLite + CAS. ``append`` is synchronous enqueue/commit:
producers never block on I/O behind this interface (backpressure lives in the
writer, design §10.2).
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from zugzwang_core.domain.events import EventEnvelope


@runtime_checkable
class EventSink(Protocol):
    def next_sequence(
        self,
        stream_type: Literal["experiment", "run", "episode", "step", "attempt"],
        stream_id: str,
    ) -> int: ...

    def append(self, envelope: EventEnvelope) -> None: ...

    def all_events(self) -> tuple[EventEnvelope, ...]: ...


class InMemoryEventSink:
    """M0 sink. Order of append within a stream is preserved."""

    def __init__(self) -> None:
        self._events: list[EventEnvelope] = []
        self._sequences: dict[tuple[str, str], int] = {}

    def next_sequence(
        self,
        stream_type: Literal["experiment", "run", "episode", "step", "attempt"],
        stream_id: str,
    ) -> int:
        key = (stream_type, stream_id)
        current = self._sequences.get(key, -1)
        self._sequences[key] = current + 1
        return current + 1

    def append(self, envelope: EventEnvelope) -> None:
        self._events.append(envelope)

    def all_events(self) -> tuple[EventEnvelope, ...]:
        return tuple(self._events)
