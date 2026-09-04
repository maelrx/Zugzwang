"""Single logical writer with a bounded queue (design §10.2).

Episode tasks enqueue persistence commands; one writer task drains the queue
into SQLite + CAS. Events and their projections commit in the same SQL
transaction (design §11.5). Backpressure: a full queue blocks producers.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.engine import Connection

from zugzwang_core.domain.errors import PersistenceError
from zugzwang_core.domain.events import EventEnvelope, EventStreamRef

from .repositories import (
    ArtifactRepository,
    AttemptRepository,
    CheckpointRepository,
    EpisodeRepository,
    EventRepository,
    MetricObservationRepository,
    RunRepository,
    SearchEdgeRepository,
    SearchNodeRepository,
    SearchRetrievalEventRepository,
    SearchSessionRepository,
    StepRepository,
)

StreamType = Literal["experiment", "run", "episode", "step", "attempt"]


@dataclass(frozen=True, slots=True)
class AppendEventCommand:
    envelope: EventEnvelope


@dataclass(frozen=True, slots=True)
class UpsertRunCommand:
    row: dict[str, Any]
    update: bool = False


@dataclass(frozen=True, slots=True)
class InsertEpisodeCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpdateEpisodeCommand:
    episode_id: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertStepCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpdateStepCommand:
    step_id: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertAttemptCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpdateAttemptCommand:
    attempt_id: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertArtifactCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertMetricCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertCheckpointCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertSearchSessionCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpdateSearchSessionCommand:
    search_session_id: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertSearchNodeCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertSearchEdgeCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertSearchRetrievalEventCommand:
    row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CommitStepCommand:
    """Atomic commit unit: step projection + episode projection + checkpoint + event."""

    step_id: str
    step_values: dict[str, Any]
    episode_id: str
    episode_values: dict[str, Any]
    envelope: EventEnvelope
    checkpoint_row: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FinalizeEpisodeCommand:
    episode_id: str
    episode_values: dict[str, Any]
    envelope: EventEnvelope


@dataclass(frozen=True, slots=True)
class FinalizeRunCommand:
    run_id: str
    run_values: dict[str, Any]
    envelope: EventEnvelope


PersistenceCommand = (
    AppendEventCommand
    | UpsertRunCommand
    | InsertEpisodeCommand
    | UpdateEpisodeCommand
    | InsertStepCommand
    | UpdateStepCommand
    | InsertAttemptCommand
    | UpdateAttemptCommand
    | InsertArtifactCommand
    | InsertMetricCommand
    | InsertCheckpointCommand
    | CommitStepCommand
    | FinalizeEpisodeCommand
    | FinalizeRunCommand
    | InsertSearchSessionCommand
    | UpdateSearchSessionCommand
    | InsertSearchNodeCommand
    | InsertSearchEdgeCommand
    | InsertSearchRetrievalEventCommand
)


@dataclass(slots=True)
class PersistenceWriter:
    """Drains a bounded queue into SQLite; the only SQLite writer in-process."""

    _runs: RunRepository = field(init=False)
    _episodes: EpisodeRepository = field(init=False)
    _steps: StepRepository = field(init=False)
    _attempts: AttemptRepository = field(init=False)
    _events: EventRepository = field(init=False)
    _metrics: MetricObservationRepository = field(init=False)
    _checkpoints: CheckpointRepository = field(init=False)
    _artifacts: ArtifactRepository | None = field(init=False, default=None)
    _search_sessions: SearchSessionRepository = field(init=False)
    _search_nodes: SearchNodeRepository = field(init=False)
    _search_edges: SearchEdgeRepository = field(init=False)
    _search_retrieval_events: SearchRetrievalEventRepository = field(init=False)
    _queue: asyncio.Queue[PersistenceCommand] = field(init=False)
    _task: asyncio.Task[None] | None = field(init=False, default=None)
    _stop: asyncio.Event = field(init=False)
    _processed: int = field(init=False, default=0)
    _errors: list[str] = field(init=False)

    def __init__(
        self,
        *,
        runs: RunRepository,
        episodes: EpisodeRepository,
        steps: StepRepository,
        attempts: AttemptRepository,
        events: EventRepository,
        metrics: MetricObservationRepository,
        checkpoints: CheckpointRepository,
        artifacts_repo: Any = None,
        queue_size: int = 4096,
    ) -> None:
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._attempts = attempts
        self._events = events
        self._metrics = metrics
        self._checkpoints = checkpoints
        self._artifacts = artifacts_repo
        engine = runs.engine  # repositories share the same SQLAlchemy engine
        self._search_sessions = SearchSessionRepository(engine)
        self._search_nodes = SearchNodeRepository(engine)
        self._search_edges = SearchEdgeRepository(engine)
        self._search_retrieval_events = SearchRetrievalEventRepository(engine)
        self._queue = asyncio.Queue(maxsize=queue_size)
        self._task = None
        self._stop = asyncio.Event()
        self._processed = 0
        self._errors = []

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._drain(), name="persistence-writer")

    async def stop(self, drain: bool = True) -> None:
        self._stop.set()
        if drain:
            await self._queue.join()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def enqueue(self, command: PersistenceCommand) -> None:
        """Blocking-safe enqueue for async producers (put_nowait + backpressure)."""
        try:
            self._queue.put_nowait(command)
        except asyncio.QueueFull as exc:
            raise PersistenceError(
                "persistence queue is full; writers must slow down",
                technical_context=f"size={self._queue.qsize()}",
            ) from exc

    async def enqueue_async(self, command: PersistenceCommand) -> None:
        await self._queue.put(command)

    async def flush(self) -> None:
        await self._queue.join()

    async def _drain(self) -> None:
        while not self._stop.is_set():
            try:
                command = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.005)
                continue
            try:
                self._apply(command)
            except Exception as exc:
                self._errors.append(f"{type(command).__name__}: {exc}")
            finally:
                self._queue.task_done()

    def _apply(self, command: PersistenceCommand) -> None:
        with self._runs.connect() as connection, connection.begin():
            self._apply_command(command, connection)

    def _apply_command(self, command: PersistenceCommand, connection: Connection) -> None:
        if isinstance(command, AppendEventCommand):
            envelope = self._stamped(command.envelope, connection)
            self._events.append_event(_event_row(envelope), connection)
            return
        if isinstance(command, UpsertRunCommand):
            if command.update:
                values = {k: v for k, v in command.row.items() if k != "run_id"}
                self._runs.update_run(command.row["run_id"], values, connection)
            else:
                self._runs.insert_run(command.row, connection)
            return
        if isinstance(command, InsertEpisodeCommand):
            self._episodes.insert_episode(command.row, connection)
            return
        if isinstance(command, UpdateEpisodeCommand):
            self._episodes.update_episode(command.episode_id, command.values, connection)
            return
        if isinstance(command, InsertStepCommand):
            self._steps.insert_step(command.row, connection)
            return
        if isinstance(command, UpdateStepCommand):
            self._steps.update_step(command.step_id, command.values, connection)
            return
        if isinstance(command, InsertAttemptCommand):
            self._attempts.insert_attempt(command.row, connection)
            return
        if isinstance(command, UpdateAttemptCommand):
            self._attempts.update_attempt(command.attempt_id, command.values, connection)
            return
        if isinstance(command, InsertArtifactCommand):
            if self._artifacts is None:
                raise PersistenceError(
                    "artifact registration requires an ArtifactRepository in the writer"
                )
            self._artifacts.insert_artifact(command.row, connection)
            return
        if isinstance(command, InsertMetricCommand):
            self._metrics.insert(command.row, connection)
            return
        if isinstance(command, InsertCheckpointCommand):
            self._checkpoints.insert(command.row, connection)
            return
        if isinstance(command, InsertSearchSessionCommand):
            self._search_sessions.insert(command.row, connection)
            return
        if isinstance(command, UpdateSearchSessionCommand):
            self._search_sessions.update(command.search_session_id, command.values, connection)
            return
        if isinstance(command, InsertSearchNodeCommand):
            self._search_nodes.insert(command.row, connection)
            return
        if isinstance(command, InsertSearchEdgeCommand):
            self._search_edges.insert(command.row, connection)
            return
        if isinstance(command, InsertSearchRetrievalEventCommand):
            self._search_retrieval_events.insert(command.row, connection)
            return
        if isinstance(command, CommitStepCommand):
            self._steps.update_step(command.step_id, command.step_values, connection)
            self._episodes.update_episode(command.episode_id, command.episode_values, connection)
            self._events.append_event(
                _event_row(self._stamped(command.envelope, connection)), connection
            )
            self._checkpoints.insert(command.checkpoint_row, connection)
            return
        if isinstance(command, FinalizeEpisodeCommand):
            self._episodes.update_episode(command.episode_id, command.episode_values, connection)
            self._events.append_event(
                _event_row(self._stamped(command.envelope, connection)), connection
            )
            return
        self._runs.update_run(command.run_id, command.run_values, connection)
        self._events.append_event(
            _event_row(self._stamped(command.envelope, connection)), connection
        )

    def _stamped(self, envelope: EventEnvelope, connection: Connection) -> EventEnvelope:
        """Assign the authoritative sequence (max+1) inside this transaction."""
        sequence = (
            self._events.max_sequence(envelope.stream.type, envelope.stream.id, connection) + 1
        )
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

    @property
    def processed(self) -> int:
        return self._processed

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(self._errors)


def _event_row(envelope: EventEnvelope) -> dict[str, Any]:
    return {
        "event_id": envelope.event_id,
        "run_id": envelope.context.run_id,
        "episode_id": envelope.context.episode_id,
        "step_id": envelope.context.step_id,
        "attempt_id": envelope.context.attempt_id,
        "stream_type": envelope.stream.type,
        "stream_id": envelope.stream.id,
        "sequence_no": envelope.stream.sequence,
        "event_type": envelope.event_type,
        "event_version": envelope.event_version,
        "occurred_at": envelope.occurred_at.isoformat(),
        "payload_json": envelope.payload,
        "artifact_refs_json": list(envelope.artifact_refs),
        "trace_id": envelope.context.trace_id,
    }
