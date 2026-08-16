"""Repositories over SQLAlchemy Core (ADR-013).

Explicit statements, small surfaces, no ORM sessions, no lazy loading.
Rows are mapped to plain dictionaries; domain models stay out of SQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Engine

from zugzwang_core.domain.errors import PersistenceError

from .tables import (
    artifacts,
    attempts,
    checkpoints,
    episodes,
    events,
    metric_observations,
    runs,
    steps,
)


class BaseRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager  # pyright: ignore[reportDeprecated] - stdlib contextmanager is the intended tool here
    def connect(self) -> Iterator[Connection]:
        try:
            connection = self._engine.connect()
        except Exception as exc:
            raise PersistenceError(
                "cannot connect to the operational database",
                technical_context=str(exc),
            ) from exc
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager  # pyright: ignore[reportDeprecated] - stdlib contextmanager is the intended tool here
    def _target(self, connection: Connection | None) -> Iterator[Connection]:
        """Use the caller's connection (writer transaction) or a fresh one.

        A fresh connection commits on success (the writer owns its own
        transactions when it passes a connection in).
        """
        if connection is not None:
            yield connection
        else:
            with self.connect() as fresh, fresh.begin():
                yield fresh


class SchemaManager(BaseRepository):
    """Runs Alembic migrations explicitly (never create_all in production)."""

    def upgrade(self) -> None:
        from alembic import command
        from alembic.config import Config

        from .. import migration_dir

        config = Config()
        config.set_main_option("script_location", str(migration_dir))
        config.set_main_option(
            "sqlalchemy.url",
            f"sqlite:///{self._engine.url.database}",
        )
        try:
            command.upgrade(config, "head")
        except Exception as exc:
            raise PersistenceError("database migration failed", technical_context=str(exc)) from exc

    def current_revision(self) -> str | None:
        from alembic.migration import MigrationContext

        try:
            with self._engine.connect() as connection:
                context = MigrationContext.configure(connection)
                revision = context.get_current_revision()
                return str(revision) if revision else None
        except Exception:
            return None

    def tables_exist(self) -> bool:
        from sqlalchemy import inspect

        inspector = inspect(self._engine)
        return bool(set(inspector.get_table_names()))


class RunRepository(BaseRepository):
    def insert_run(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(runs.insert().values(**row))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            result = connection.execute(select(runs).where(runs.c.run_id == run_id))
            row = result.mappings().first()
            return dict(row) if row is not None else None

    def update_run(
        self, run_id: str, values: dict[str, Any], connection: Connection | None = None
    ) -> None:
        with self._target(connection) as target:
            target.execute(update(runs).where(runs.c.run_id == run_id).values(**values))

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(runs).order_by(runs.c.started_at.desc()).limit(limit)
            )
            return [dict(row) for row in result.mappings()]


class EpisodeRepository(BaseRepository):
    def insert_episode(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(episodes.insert().values(**row))

    def get_episode(self, episode_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            result = connection.execute(select(episodes).where(episodes.c.episode_id == episode_id))
            row = result.mappings().first()
            return dict(row) if row is not None else None

    def update_episode(
        self, episode_id: str, values: dict[str, Any], connection: Connection | None = None
    ) -> None:
        with self._target(connection) as target:
            target.execute(
                update(episodes).where(episodes.c.episode_id == episode_id).values(**values)
            )

    def for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(episodes).where(episodes.c.run_id == run_id).order_by(episodes.c.ordinal)
            )
            return [dict(row) for row in result.mappings()]


class StepRepository(BaseRepository):
    def insert_step(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(steps.insert().values(**row))

    def update_step(
        self, step_id: str, values: dict[str, Any], connection: Connection | None = None
    ) -> None:
        with self._target(connection) as target:
            target.execute(update(steps).where(steps.c.step_id == step_id).values(**values))

    def for_episode(self, episode_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(steps).where(steps.c.episode_id == episode_id).order_by(steps.c.ordinal)
            )
            return [dict(row) for row in result.mappings()]


class AttemptRepository(BaseRepository):
    def insert_attempt(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(attempts.insert().values(**row))

    def update_attempt(
        self, attempt_id: str, values: dict[str, Any], connection: Connection | None = None
    ) -> None:
        with self._target(connection) as target:
            target.execute(
                update(attempts).where(attempts.c.attempt_id == attempt_id).values(**values)
            )

    def for_step(self, step_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(attempts).where(attempts.c.step_id == step_id).order_by(attempts.c.ordinal)
            )
            return [dict(row) for row in result.mappings()]


class EventRepository(BaseRepository):
    def append_event(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(events.insert().values(**row))

    def for_stream(
        self,
        stream_type: Literal["experiment", "run", "episode", "step", "attempt"],
        stream_id: str,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(events)
                .where(events.c.stream_type == stream_type, events.c.stream_id == stream_id)
                .order_by(events.c.sequence_no)
            )
            return [dict(row) for row in result.mappings()]

    def max_sequence(
        self,
        stream_type: Literal["experiment", "run", "episode", "step", "attempt"],
        stream_id: str,
        connection: Connection | None = None,
    ) -> int:
        with self._target(connection) as target:
            result = target.execute(
                select(func.max(events.c.sequence_no)).where(
                    events.c.stream_type == stream_type, events.c.stream_id == stream_id
                )
            )
            value = result.scalar()
            return int(value) if value is not None else -1

    def for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(events).where(events.c.run_id == run_id).order_by(events.c.event_id)
            )
            return [dict(row) for row in result.mappings()]


class ArtifactRepository(BaseRepository):
    def insert_artifact(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(artifacts.insert().values(**row))

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            result = connection.execute(
                select(artifacts).where(artifacts.c.artifact_id == artifact_id)
            )
            row = result.mappings().first()
            return dict(row) if row is not None else None

    def referenced_ids(self) -> set[str]:
        """All artifact ids referenced by events, steps, episodes, runs and metrics."""
        referenced: set[str] = set()
        with self.connect() as connection:
            for row in connection.execute(select(events.c.artifact_refs_json)):
                refs: list[Any] = list(row[0] or [])
                referenced.update(str(ref) for ref in refs)
            for column in (
                episodes.c.initial_state_artifact_id,
                episodes.c.final_state_artifact_id,
                steps.c.observation_artifact_id,
                steps.c.transition_artifact_id,
                attempts.c.request_artifact_id,
                attempts.c.response_artifact_id,
                metric_observations.c.provenance_artifact_id,
                runs.c.resolved_manifest_artifact_id,
                checkpoints.c.state_artifact_id,
            ):
                for row in connection.execute(select(column)):
                    if row[0]:
                        referenced.add(str(row[0]))
        return {r for r in referenced if r.startswith("sha256:")}


class MetricObservationRepository(BaseRepository):
    def insert(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(metric_observations.insert().values(**row))

    def for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            result = connection.execute(
                select(metric_observations).where(metric_observations.c.run_id == run_id)
            )
            return [dict(row) for row in result.mappings()]


class CheckpointRepository(BaseRepository):
    def insert(self, row: dict[str, Any], connection: Connection | None = None) -> None:
        with self._target(connection) as target:
            target.execute(checkpoints.insert().values(**row))

    def latest_for_stream(
        self,
        stream_type: Literal["experiment", "run", "episode", "step", "attempt"],
        stream_id: str,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            result = connection.execute(
                select(checkpoints)
                .where(
                    checkpoints.c.stream_type == stream_type,
                    checkpoints.c.stream_id == stream_id,
                )
                .order_by(checkpoints.c.checkpoint_id.desc())
                .limit(1)
            )
            row = result.mappings().first()
            return dict(row) if row is not None else None
