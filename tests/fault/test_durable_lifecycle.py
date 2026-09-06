"""Fault injection and interrupt/resume tests (design §24.1, ADR-031).

Invariant: recovery never applies an action twice and never creates a
dangling reference (NFR-003, NFR-004).
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.workspace import Workspace

MANIFEST = Path(__file__).resolve().parents[2] / "experiments" / "fake-smoke.yaml"


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    ws = Workspace.from_root(tmp_path / "ws")
    ws.ensure_layout()
    return ws


async def _start(workspace: Workspace, stop_event: asyncio.Event):
    services = DurableRunServices(workspace, PluginRegistry())
    return await services.start(StartRunCommand(manifest_path=MANIFEST), stop_event)


def _db(workspace: Workspace) -> sqlite3.Connection:
    return sqlite3.connect(workspace.data_dir / "state.db")


def _committed_actions(workspace: Workspace, episode_id: str) -> list[str]:
    connection = _db(workspace)
    rows = connection.execute(
        "SELECT action_json, status FROM steps WHERE episode_id=? ORDER BY ordinal",
        (episode_id,),
    ).fetchall()
    return [r[0] for r in rows if r[1] == "COMMITTED"]


@pytest.mark.fault
class TestDurableLifecycle:
    @pytest.mark.asyncio
    async def test_full_run_persists_everything(self, workspace: Workspace) -> None:
        result = await _start(workspace, asyncio.Event())
        assert result.status == "COMPLETED"
        connection = _db(workspace)
        run = connection.execute(
            "SELECT status FROM runs WHERE run_id=?", (result.run_id,)
        ).fetchone()
        assert run[0] == "COMPLETED"
        assert connection.execute("SELECT count(*) FROM steps").fetchone()[0] == 6
        assert (
            connection.execute("SELECT count(*) FROM steps WHERE status='COMMITTED'").fetchone()[0]
            == 6
        )
        assert connection.execute("SELECT count(*) FROM attempts").fetchone()[0] == 6
        assert connection.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 6
        # events have monotonic sequences per stream
        streams = connection.execute(
            "SELECT stream_type, stream_id, sequence_no FROM events ORDER BY stream_id, sequence_no"
        ).fetchall()
        seen: dict[tuple[str, str], int] = {}
        for stream_type, stream_id, sequence in streams:
            key = (stream_type, stream_id)
            assert sequence == seen.get(key, -1) + 1, f"sequence gap in {key}"
            seen[key] = sequence

    @pytest.mark.asyncio
    async def test_interrupt_mid_run_and_resume(self, workspace: Workspace) -> None:
        stop_event = asyncio.Event()

        async def interrupt_after_delay() -> None:
            await asyncio.sleep(0.05)
            stop_event.set()

        from zugzwang_runtime.application.durable_services import DurableRunServices

        services = DurableRunServices(workspace, PluginRegistry())
        interrupt_task = asyncio.create_task(interrupt_after_delay())
        first = await services.start(StartRunCommand(manifest_path=MANIFEST), stop_event)
        await interrupt_task

        connection = _db(workspace)
        run_status = connection.execute(
            "SELECT status FROM runs WHERE run_id=?", (first.run_id,)
        ).fetchone()[0]
        assert run_status in {"INTERRUPTED", "FAILED", "COMPLETED"}

        resumed = await services.resume(first.run_id, MANIFEST, asyncio.Event())
        assert resumed.status == "COMPLETED"

        committed = connection.execute(
            "SELECT count(*) FROM steps WHERE status='COMMITTED'"
        ).fetchone()[0]
        assert committed == 6, "committed steps must total exactly 6 after resume"

        episodes = connection.execute(
            "SELECT episode_id FROM episodes WHERE run_id=?", (first.run_id,)
        ).fetchall()
        for (episode_id,) in episodes:
            actions = connection.execute(
                "SELECT action_json FROM steps WHERE episode_id=? AND status='COMMITTED' ORDER BY ordinal",
                (episode_id,),
            ).fetchall()
            values = [a[0] for a in actions]
            assert values == [
                '{"action": "inc"}',
                '{"action": "inc"}',
                '{"action": "inc"}',
            ], f"episode {episode_id} replayed or duplicated actions: {values}"

    @pytest.mark.asyncio
    async def test_resume_idempotent_on_completed_run(self, workspace: Workspace) -> None:
        first = await _start(workspace, asyncio.Event())
        services = DurableRunServices(workspace, PluginRegistry())
        resumed = await services.resume(first.run_id, MANIFEST, asyncio.Event())
        assert resumed.status == "COMPLETED"
        connection = _db(workspace)
        assert connection.execute("SELECT count(*) FROM steps").fetchone()[0] == 6

    @pytest.mark.asyncio
    async def test_cancel_run(self, workspace: Workspace) -> None:
        """Cancel an interrupted (non-terminal) run."""
        from zugzwang_runtime.application.durable_services import DurableRunServices
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule

        stop_event = asyncio.Event()

        async def interrupt_after_delay() -> None:
            await asyncio.sleep(0.05)
            stop_event.set()

        from zugzwang_runtime.application.commands import ResolveExperimentCommand
        from zugzwang_runtime.application.services import ResolveExperimentService
        from zugzwang_runtime.artifacts.cas import ContentAddressedStore
        from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
        from zugzwang_runtime.execution.rate_limiting import RateLimiter
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            AttemptRepository,
            CheckpointRepository,
            EpisodeRepository,
            EventRepository,
            MetricObservationRepository,
            RunRepository,
            SchemaManager,
            StepRepository,
        )
        from zugzwang_runtime.persistence.writer import PersistenceWriter

        db = Database(workspace.data_dir / "state.db")
        engine = db.open()
        SchemaManager(engine).upgrade()
        writer = PersistenceWriter(
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            attempts=AttemptRepository(engine),
            events=EventRepository(engine),
            metrics=MetricObservationRepository(engine),
            checkpoints=CheckpointRepository(engine),
        )
        await writer.start()
        backend = DeterministicModelBackend(
            rules=(FakeBackendRule(when={"fingerprint_contains": "fake-direct"}, output="inc"),),
            latency_seconds=0.03,
        )
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(manifest_path=MANIFEST)
        )
        coordinator = DurableRunCoordinator(
            registry=PluginRegistry(),
            backend=backend,
            writer=writer,
            event_sink=PersistentEventSink(EventRepository(engine), writer),
            artifact_store=ContentAddressedStore(workspace.objects_dir()),
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            checkpoints=CheckpointRepository(engine),
            rate_limiter=RateLimiter(),
        )
        interrupt_task = asyncio.create_task(interrupt_after_delay())
        run_id = await coordinator.start_and_run(resolved, resolved.conditions[0], stop_event)
        await interrupt_task
        await writer.flush()
        await writer.stop()

        services = DurableRunServices(workspace, PluginRegistry())
        summary = services.cancel(run_id)
        assert summary.status == "CANCELED"


@pytest.mark.fault
class TestArtifactCrashProtocol:
    @pytest.mark.asyncio
    async def test_failed_put_leaves_no_dangling_ref(self, tmp_path) -> None:
        """A failing CAS put must fail the step without a DB reference (NFR-003)."""
        from zugzwang_runtime.application.commands import ResolveExperimentCommand
        from zugzwang_runtime.application.services import ResolveExperimentService
        from zugzwang_runtime.execution.durable_coordinator import DurableRunCoordinator
        from zugzwang_runtime.execution.rate_limiting import RateLimiter
        from zugzwang_runtime.execution.registry import PluginRegistry
        from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            AttemptRepository,
            CheckpointRepository,
            EpisodeRepository,
            EventRepository,
            MetricObservationRepository,
            RunRepository,
            SchemaManager,
            StepRepository,
        )
        from zugzwang_runtime.persistence.writer import PersistenceWriter

        ws = Workspace.from_root(tmp_path / "ws")
        ws.ensure_layout()
        db = Database(ws.data_dir / "state.db")
        engine = db.open()
        SchemaManager(engine).upgrade()

        class AlwaysFailStore:
            def put(self, payload, **kwargs):
                raise RuntimeError("injected CAS failure")

            def get(self, ref):
                raise RuntimeError("injected CAS failure")

        writer = PersistenceWriter(
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            attempts=AttemptRepository(engine),
            events=EventRepository(engine),
            metrics=MetricObservationRepository(engine),
            checkpoints=CheckpointRepository(engine),
        )
        await writer.start()
        sink = PersistentEventSink(EventRepository(engine), writer)
        backend = DeterministicModelBackend(
            rules=(FakeBackendRule(when={"fingerprint_contains": "fake-direct"}, output="inc"),)
        )
        resolved = ResolveExperimentService(PluginRegistry()).resolve(
            ResolveExperimentCommand(manifest_path=MANIFEST)
        )
        coordinator = DurableRunCoordinator(
            registry=PluginRegistry(),
            backend=backend,
            writer=writer,
            event_sink=sink,
            artifact_store=AlwaysFailStore(),
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            checkpoints=CheckpointRepository(engine),
            rate_limiter=RateLimiter(),
        )
        await coordinator.start_and_run(resolved, resolved.conditions[0], asyncio.Event())
        await writer.flush()
        await writer.stop()

        connection = _db(ws)
        # no step can be COMMITTED because the CAS put failed before the SQL commit
        committed = connection.execute(
            "SELECT count(*) FROM steps WHERE status='COMMITTED'"
        ).fetchone()[0]
        assert committed == 0
        # no dangling references: every stored ref points to a registered artifact
        import json as _json

        refs = connection.execute(
            "SELECT artifact_refs_json FROM events WHERE artifact_refs_json != '[]'"
        ).fetchall()
        known = {
            row[0] for row in connection.execute("SELECT artifact_id FROM artifacts").fetchall()
        }
        dangling = [
            ref
            for (refs_json,) in refs
            for ref in (refs_json if isinstance(refs_json, list) else _json.loads(refs_json))
            if ref not in known
        ]
        assert dangling == [], "event refs point to missing artifacts: " + repr(dangling)
