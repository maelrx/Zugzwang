"""Durable application services (M1): start, resume, cancel, list, show, db.

These services own the persistence wiring: database bootstrap, single
writer, CAS, coordinator. The CLI only passes commands in.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from zugzwang_core.domain.artifacts import ArtifactPayload
from zugzwang_core.domain.manifests import ResolvedCondition, ResolvedManifest

from ..artifacts.cas import ContentAddressedStore
from ..execution.durable_coordinator import DurableRunCoordinator
from ..execution.rate_limiting import RateLimiter
from ..execution.registry import PluginRegistry
from ..fakes import DeterministicModelBackend
from ..persistence.database import Database
from ..persistence.event_sink import PersistentEventSink
from ..persistence.repositories import (
    CheckpointRepository,
    EpisodeRepository,
    EventRepository,
    RunRepository,
    SchemaManager,
    StepRepository,
)
from ..persistence.writer import PersistenceWriter
from ..workspace import Workspace
from .commands import ResolveExperimentCommand, RunResult, StartRunCommand
from .services import ResolveExperimentService


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    status: str
    condition_id: str
    protocol_hash: str
    declared_assistance: str
    started_at: str | None
    finished_at: str | None
    episodes: int = 0
    steps_committed: int = 0
    attempts: int = 0
    events: int = 0


class DurableRunServices:
    """Wires persistence components for one workspace."""

    def __init__(self, workspace: Workspace, registry: PluginRegistry) -> None:
        self._workspace = workspace
        self._registry = registry
        workspace.ensure_layout()
        self._database = Database(workspace.data_dir / "state.db")
        engine = self._database.open()
        self._schema = SchemaManager(engine)
        self._schema.upgrade()
        self._runs = RunRepository(engine)
        self._episodes = EpisodeRepository(engine)
        self._steps = StepRepository(engine)
        self._events = EventRepository(engine)
        self._checkpoints = CheckpointRepository(engine)
        self._cas = ContentAddressedStore(workspace.objects_dir())

    @property
    def runs(self) -> RunRepository:
        return self._runs

    @property
    def episodes(self) -> EpisodeRepository:
        return self._episodes

    @property
    def steps(self) -> StepRepository:
        return self._steps

    @property
    def events(self) -> EventRepository:
        return self._events

    @property
    def cas(self) -> ContentAddressedStore:
        return self._cas

    @property
    def database_engine(self):
        return self._database.engine()

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    def _build_writer(self) -> PersistenceWriter:
        from ..persistence.repositories import (
            ArtifactRepository,
            AttemptRepository,
            MetricObservationRepository,
        )

        return PersistenceWriter(
            runs=self._runs,
            episodes=self._episodes,
            steps=self._steps,
            attempts=AttemptRepository(self._database.engine()),
            events=self._events,
            metrics=MetricObservationRepository(self._database.engine()),
            checkpoints=self._checkpoints,
            artifacts_repo=ArtifactRepository(self._database.engine()),
        )

    async def start(self, command: StartRunCommand, stop_event: asyncio.Event) -> RunResult:
        self._workspace.ensure_layout()
        self._schema.upgrade()
        resolved = self._resolve(command)

        writer = self._build_writer()
        await writer.start()
        event_sink = PersistentEventSink(self._events, writer)
        rate_limiter = RateLimiter()
        condition_for_backend = (
            resolved.conditions[command.condition_index]
            if command.condition_index is not None
            else resolved.conditions[0]
        )
        backend = self._backend_for(condition_for_backend)
        coordinator = DurableRunCoordinator(
            registry=self._registry,
            backend=backend,
            writer=writer,
            event_sink=event_sink,
            artifact_store=self._cas,
            runs=self._runs,
            episodes=self._episodes,
            steps=self._steps,
            checkpoints=self._checkpoints,
            rate_limiter=rate_limiter,
        )

        if command.condition_index is not None:
            conditions = (resolved.conditions[command.condition_index],)
        else:
            conditions = resolved.conditions

        resolved_artifact = self._cas.put(
            ArtifactPayload(
                media_type="application/vnd.zugzwang.manifest-resolved+json",
                data=resolved.model_dump_json().encode("utf-8"),
            )
        )
        last_run_id: str | None = None
        for condition in conditions:
            run_id = await coordinator.start_and_run(resolved, condition, stop_event)
            self._runs.update_run(
                run_id, {"resolved_manifest_artifact_id": resolved_artifact.as_id()}
            )
            last_run_id = run_id
        await writer.flush()
        await writer.stop()
        if last_run_id is None:
            raise ValueError("no conditions to run")
        row = self._runs.get_run(last_run_id)
        return self._run_result(row)

    async def resume(
        self, run_id: str, manifest_path: Path, stop_event: asyncio.Event
    ) -> RunResult:
        self._schema.upgrade()
        resolved = ResolveExperimentService(self._registry).resolve(
            ResolveExperimentCommand(manifest_path=manifest_path)
        )

        writer = self._build_writer()
        await writer.start()
        event_sink = PersistentEventSink(self._events, writer)
        backend = DeterministicModelBackend(rules=_default_fake_rules())
        coordinator = DurableRunCoordinator(
            registry=self._registry,
            backend=backend,
            writer=writer,
            event_sink=event_sink,
            artifact_store=self._cas,
            runs=self._runs,
            episodes=self._episodes,
            steps=self._steps,
            checkpoints=self._checkpoints,
            rate_limiter=RateLimiter(),
        )
        await coordinator.resume(run_id, resolved, stop_event)
        await writer.flush()
        await writer.stop()
        row = self._runs.get_run(run_id)
        return self._run_result(row)

    def cancel(self, run_id: str) -> RunSummary:
        from zugzwang_core.domain.state_machines import RunState

        row = self._runs.get_run(run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found")
        if row["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
            raise ValueError(f"run {run_id} is already {row['status']}")
        self._runs.update_run(run_id, {"status": RunState.CANCELED.value})
        return self.summary(run_id)

    def list_runs(self, limit: int = 50) -> list[RunSummary]:
        return [self.summary(row["run_id"]) for row in self._runs.list_runs(limit)]

    def summary(self, run_id: str) -> RunSummary:
        row = self._runs.get_run(run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found")
        episodes = self._episodes.for_run(run_id)
        steps_committed = 0
        attempts = 0
        for episode in episodes:
            steps_committed += sum(
                1
                for s in self._steps.for_episode(episode["episode_id"])
                if s["status"] == "COMMITTED"
            )
        events = len(self._events.for_run(run_id))
        return RunSummary(
            run_id=row["run_id"],
            status=row["status"],
            condition_id=row["condition_id"],
            protocol_hash=row["protocol_hash"],
            declared_assistance=row["declared_assistance"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            episodes=len(episodes),
            steps_committed=steps_committed,
            attempts=attempts,
            events=events,
        )

    def db_status(self) -> dict[str, object]:
        return {
            "revision": self._schema.current_revision(),
            "tables_exist": self._schema.tables_exist(),
            "path": str(self._database.path),
        }

    def db_upgrade(self) -> dict[str, object]:
        self._schema.upgrade()
        return self.db_status()

    def _backend_for(self, condition: ResolvedCondition) -> Any:
        """Build the provider backend for a condition's model player (M3+)."""
        for player in condition.players.values():
            if player.model is None or player.model.backend is None:
                continue
            backend_id = player.model.backend
            if backend_id == "fake.backend":
                return DeterministicModelBackend(rules=_default_fake_rules())
            backend_config_raw = condition.task.config.get("backend_config")
            backend_config: dict[str, Any] = (
                cast(dict[str, Any], backend_config_raw)
                if isinstance(backend_config_raw, dict)
                else {}
            )
            if backend_id == "provider.opencode":
                from zgw_provider_opencode.adapter import OpenCodeBackend

                return OpenCodeBackend(
                    base_url=str(backend_config.get("base_url", "http://127.0.0.1:4100")),
                    provider_id=str(backend_config.get("provider_id", "opencode")),
                    timeout_seconds=float(backend_config.get("timeout_seconds", 300) or 300),
                    image_input=bool(backend_config.get("image_input", False)),
                )
            if backend_id == "provider.openai_compatible":
                from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

                from ..security import resolve_secret

                return OpenAiCompatibleBackend(
                    base_url=str(backend_config.get("base_url", "")),
                    api_key=resolve_secret(
                        str(backend_config["api_key"]) if backend_config.get("api_key") else None
                    ),
                    image_input=bool(backend_config.get("image_input", False)),
                )
        return DeterministicModelBackend(rules=_default_fake_rules())

    def _resolve(self, command: StartRunCommand) -> ResolvedManifest:
        return ResolveExperimentService(self._registry).resolve(
            ResolveExperimentCommand(
                manifest_path=command.manifest_path,
                patches=command.patches,
            )
        )

    def _run_result(self, row: dict[str, Any] | None) -> RunResult:
        if row is None:
            raise ValueError("run row missing after execution")
        episodes = self._episodes.for_run(row["run_id"])
        return RunResult(
            run_id=row["run_id"],
            status=row["status"],
            experiment_name="",
            condition_id=row["condition_id"],
            episodes_completed=sum(1 for e in episodes if e["status"] == "COMPLETED"),
            episodes_failed=sum(1 for e in episodes if e["status"] == "FAILED"),
            events_count=len(self._events.for_run(row["run_id"])),
            output_dir=str(self._workspace.run_dir(row["run_id"])),
            started_at=row["started_at"] or "",
            finished_at=row["finished_at"] or "",
        )


def _default_fake_rules():
    # Counter domain: always increment.
    # Chess domain: cycle a small legal white opening script so full games
    # with the fake backend stay legal regardless of the opponent's replies.
    import json as _json

    from ..fakes import FakeBackendRule

    chess_script = ("g1f3", "g2g3", "f1g2", "b1c3", "d2d3", "e1g1")
    black_script = ("g8f6", "g7g6", "f8g7", "b8c6", "d7d6", "e8g8")
    structured_output = _json.dumps(
        {
            "analysis": "opening move",
            "candidates": [{"move": "g1f3", "score": 0.1}],
            "chosen_move": "g1f3",
        }
    )
    return (
        FakeBackendRule(when={"fingerprint_contains": "fake-direct"}, output="inc"),
        FakeBackendRule(when={"fingerprint_contains": "chess-grounded"}, output="e2e4"),
        FakeBackendRule(when={"fingerprint_contains": "chess-repair"}, output="e2e4"),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-structured"}, output=structured_output
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-reconstruct"},
            output=_json.dumps(
                {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"}
            ),
        ),
        *[
            FakeBackendRule(
                when={
                    "call_index_modulo": [len(black_script), index],
                    "fingerprint_contains": "chess-direct:black",
                },
                output=move,
            )
            for index, move in enumerate(black_script)
        ],
        *[
            FakeBackendRule(
                when={"call_index_modulo": [len(chess_script), index]},
                output=move,
            )
            for index, move in enumerate(chess_script)
        ],
    )
