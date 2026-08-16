"""Persistent event sink: enqueues envelopes to the single writer.

Sequences come from the database (max + 1 per stream), guarded by a per-stream
lock, so concurrent producers never emit duplicate sequence numbers.
"""

from __future__ import annotations

import threading
from typing import Literal

from zugzwang_core.domain.events import EventEnvelope, EventStreamRef

from .repositories import EventRepository
from .writer import AppendEventCommand, PersistenceWriter

StreamType = Literal["experiment", "run", "episode", "step", "attempt"]


class PersistentEventSink:
    """EventSink over the PersistenceWriter.

    Sequences are authoritative in-process (seeded from the database once per
    stream) and incremented under a per-stream lock, so queue latency can
    never produce duplicate or gapped sequences.
    """

    def __init__(self, events: EventRepository, writer: PersistenceWriter) -> None:
        self._events = events
        self._writer = writer
        self._locks: dict[tuple[str, str], threading.Lock] = {}
        self._counters: dict[tuple[str, str], int] = {}
        self._buffer: list[EventEnvelope] = []

    def _lock_for(self, stream_type: str, stream_id: str) -> threading.Lock:
        key = (stream_type, stream_id)
        lock = self._locks.get(key)
        if lock is None:
            lock = threading.Lock()
            self._locks[key] = lock
        return lock

    def next_sequence(
        self,
        stream_type: StreamType,
        stream_id: str,
    ) -> int:
        """Next sequence for a stream (in-process counter, DB-seeded)."""
        key = (stream_type, stream_id)
        with self._lock_for(stream_type, stream_id):
            if key not in self._counters:
                self._counters[key] = self._events.max_sequence(stream_type, stream_id)
            self._counters[key] += 1
            return self._counters[key]

    def stamp(self, envelope: EventEnvelope) -> EventEnvelope:
        """Return a copy of the envelope with its authoritative sequence."""
        sequence = self.next_sequence(envelope.stream.type, envelope.stream.id)
        return EventEnvelope(
            schema_version=envelope.schema_version,
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
            occurred_at=envelope.occurred_at,
            stream=EventStreamRef(
                type=envelope.stream.type, id=envelope.stream.id, sequence=sequence
            ),
            context=envelope.context,
            payload=envelope.payload,
            artifact_refs=envelope.artifact_refs,
            assistance=envelope.assistance,
        )

    def append(self, envelope: EventEnvelope) -> None:
        """Enqueue an event; the writer assigns the authoritative sequence."""
        self._writer.enqueue(AppendEventCommand(envelope=envelope))
        self._buffer.append(envelope)

    async def flush(self) -> None:
        await self._writer.flush()

    def all_events(self) -> tuple[EventEnvelope, ...]:
        return tuple(self._buffer)
