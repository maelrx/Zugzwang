"""Durable application services (M1): start, resume, cancel, list, show, db.

These services own the persistence wiring: database bootstrap, single
writer, CAS, coordinator. The CLI only passes commands in.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from zugzwang_core.domain.artifacts import ArtifactPayload
from zugzwang_core.domain.manifests import ResolvedCondition, ResolvedManifest

from ..artifacts.cas import ContentAddressedStore
from ..execution.durable_coordinator import DurableRunCoordinator
from ..execution.evidence import store_artifact, store_json_artifact
from ..execution.rate_limiting import RateLimiter
from ..execution.registry import PluginRegistry
from ..fakes import DeterministicModelBackend
from ..persistence.database import Database
from ..persistence.event_sink import PersistentEventSink
from ..persistence.repositories import (
    AttemptRepository,
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
    effective_assistance: str | None = None
    assistance_violated: bool = False
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
        if workspace.wal_policy == "ephemeral":
            print(
                "aviso: workspace NAO-DURAVEL (wal_policy=ephemeral) — "
                "continuidade apos crash/falta de energia nao garantida",
                file=sys.stderr,
            )
        self._database = Database(workspace.data_dir / "state.db", wal_policy=workspace.wal_policy)
        engine = self._database.open()
        self._schema = SchemaManager(engine)
        self._schema.upgrade()
        self._runs = RunRepository(engine)
        self._episodes = EpisodeRepository(engine)
        self._steps = StepRepository(engine)
        self._attempts = AttemptRepository(engine)
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
    def attempts(self) -> AttemptRepository:
        return self._attempts

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

    def _cognitive_session_factory(
        self, observation_holder: dict[str, dict[str, Any]] | None = None
    ):
        """Factory opening one CognitiveBoard decision session per step (§26.1).

        Keeps the coordinator free of SQL/CAS wiring while the productive
        cognitive path runs through the same durable workspace: the journal,
        the CAS and the perception share this run's storage (ZGW-0101).

        ``observation_holder["current"]`` is the RUNNING condition's declared
        protocol.observation policy: ZGW-0103 R3 threads it into packet
        building so ascii/history exposure declared in the manifest actually
        reaches the model — never a silently ignored declaration (§5.1).
        """
        from zugzwang_chess.cognition import ChessPerception, PacketExposure
        from zugzwang_chess.environment.standard import StandardChessEnvironment
        from zugzwang_core.domain.canonical import hash_canonical

        from ..cognition.session import DecisionSession
        from ..persistence.cognition import CognitionJournal

        # Direct coordinator construction (resume path, fault tests) without a
        # declared observation policy falls back to the minimal exposure.
        holder = observation_holder if observation_holder is not None else {}
        exposure = PacketExposure.from_observation(holder.get("current"))
        # ZGX arms: N1 controls run with inline_child_packages OFF — the
        # mechanism under test is the inline child package, so the declared
        # toggle must reach the broker, never be silently ignored.
        cognitive_cfg = holder.get("cognitive") or {}
        inline_packages = cognitive_cfg.get("inline_child_packages") is not False

        def factory(
            *,
            run_id: str,
            episode_id: str,
            step_id: str,
            decision_ordinal: int,
            state: Any,
            strategy: Any,
            interaction_mode: str = "native_tools",
        ):
            decision_id = f"dec-{step_id}-{decision_ordinal}"[:128]
            search_session_id = f"ses-{step_id}-{decision_ordinal}"[:32]
            root_node_id = f"node_{decision_id}"[:128]
            journal = CognitionJournal(self._database)
            policy_hash = hash_canonical(
                {
                    "rules": "standard/v1",
                    "perception": "chess-perception/v0.2",
                    "strategy": strategy.strategy_id,
                }
            )
            journal.ensure_search_session(
                search_session_id=search_session_id,
                run_id=run_id,
                episode_id=episode_id,
                step_id=step_id,
                root_node_id=root_node_id,
            )
            # The decision row references the root state snapshot
            # (cb_state_snapshots FK): ensure it before opening the session.
            from zugzwang_chess.cognition import ChessPerception as _Perception

            perception = _Perception(
                environment=StandardChessEnvironment(),
                rules_version="standard/v1",
                policy_hash=policy_hash,
            )
            root_state_key, root_position_key = perception.identity_keys(state)
            journal.ensure_state_snapshot(
                state_key=root_state_key,
                state_schema_version="state/v2",
                rules_version="standard/v1",
                variant=getattr(state, "variant", "standard"),
                position_key=root_position_key,
                history_completeness="complete"
                if getattr(state, "initial_fen", "") == getattr(state, "fen", "")
                and not getattr(state, "move_stack", ())
                else "from_anchor",
                state_artifact_id=self._store_root_state_artifact(state),
            )
            return DecisionSession.open(
                decision_id=decision_id,
                step_id=step_id,
                decision_ordinal=decision_ordinal,
                search_session_id=search_session_id,
                strategy_id=strategy.strategy_id,
                strategy_version=strategy.strategy_version,
                interaction_mode=interaction_mode,
                policy_hash=policy_hash,
                config={},
                states={root_node_id: state},
                max_model_calls=max(1, int(getattr(strategy.descriptor, "max_model_calls", 4))),
                journal=journal,
                perception=ChessPerception(
                    environment=StandardChessEnvironment(),
                    rules_version="standard/v1",
                    policy_hash=policy_hash,
                    exposure=exposure,
                ),
                cas=self._cas,
                engine=self._database.engine(),
                inline_child_packages=inline_packages,
            )

        return factory

    def _reject_unsupported_observation(self, condition: ResolvedCondition) -> None:
        """Fail closed on declared exposure the chosen strategy cannot deliver
        (ZGW-0103 R3; dossier §5 acceptance: expose for real OR reject)."""
        from zugzwang_core.domain.errors import ManifestValidationError

        observation: dict[str, Any] = dict(condition.protocol.observation or {})
        position_raw = observation.get("position")
        position = cast("dict[str, Any]", position_raw) if isinstance(position_raw, dict) else {}
        if not position.get("image"):
            return
        for player in condition.players.values():
            if player.model is not None and player.model.strategy == "chess.cognitive_navigation":
                raise ManifestValidationError(
                    "protocol.observation.position.image is declared, but "
                    "chess.cognitive_navigation delivers packets without image parts; "
                    "remove the declaration or use a strategy that consumes "
                    "environment.observe",
                    technical_context=condition.condition_id,
                )

    def _code_pin(self) -> dict[str, Any]:
        """Git attribution of the executing code (ZGW-0103 R4). Best effort:
        an unavailable git context stays unknown, never an invented value."""
        import subprocess

        pin: dict[str, Any] = {"code_git_sha": None, "code_dirty": None}
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            pin["code_git_sha"] = completed.stdout.strip() or None
        except Exception:
            return pin
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            pin["code_dirty"] = 1 if status.stdout.strip() else 0
        except Exception:
            pin["code_dirty"] = None
        return pin

    def _exposure_manifest_payload(
        self, condition: ResolvedCondition, code_pin: dict[str, Any]
    ) -> dict[str, Any]:
        """Declared vs effective exposure for ONE run (ZGW-0103 R3/R4).

        ``effective`` is what the wired path serializes — for the cognitive
        strategy that is the L0 packet policy actually handed to perception —
        so downstream analysis can verify the intervention reached the model.
        """
        from zugzwang_chess.cognition import PacketExposure

        observation = dict(condition.protocol.observation or {})
        strategy_ids = [p.model.strategy for p in condition.players.values() if p.model is not None]
        if "chess.cognitive_navigation" in strategy_ids:
            exposure = PacketExposure.from_observation(observation)
            effective: dict[str, Any] = {
                "path": "l0_packet",
                "strategies": strategy_ids,
                "fen": exposure.fen,
                "piece_map": True,
                "ascii": exposure.ascii,
                "history_mode": exposure.history_mode,
                "history_plies": exposure.history_plies,
                "history_notation": exposure.history_notation,
                "legal_actions": "paginated",
                "relations": "minimal",
            }
        else:
            effective = {
                "path": "environment.observe",
                "strategies": strategy_ids,
                "declared": observation,
            }
        return {
            "schema_version": "zgw.exposure-manifest/v1",
            "condition_id": condition.condition_id,
            "declared": {"observation": observation},
            "effective": effective,
            "unsupported": [],
            "code": code_pin,
        }

    def _store_root_state_artifact(self, state: Any) -> str:
        """CAS-store one integral chess state in the canonical record form."""
        from zugzwang_chess.environment.standard import STATE_MEDIA_TYPE
        from zugzwang_core.domain.artifacts import ArtifactPayload
        from zugzwang_core.domain.canonical import canonical_json_bytes

        payload = ArtifactPayload(
            media_type=STATE_MEDIA_TYPE,
            data=canonical_json_bytes(
                {
                    "fen": state.fen,
                    "initial_fen": state.initial_fen,
                    "move_stack": list(state.move_stack),
                    "variant": state.variant,
                    "synthetic_clock": state.synthetic_clock,
                }
            ),
        )
        ref = self._cas.put(payload)
        from ..persistence.repositories import ArtifactRepository

        ArtifactRepository(self._database.engine()).insert_artifact(
            row={
                "artifact_id": ref.as_id(),
                "algorithm": "sha256",
                "size_bytes": len(payload.data),
                "media_type": payload.media_type,
                "relative_path": ref.storage_path(),
                "created_at": "2026-09-06T00:00:00Z",
            }
        )
        return ref.as_id()

    def _artifacts_repo(self):
        from ..persistence.repositories import ArtifactRepository

        return ArtifactRepository(self._database.engine())

    def _build_writer(self) -> PersistenceWriter:
        from ..persistence.repositories import (
            ArtifactRepository,
            MetricObservationRepository,
        )

        return PersistenceWriter(
            runs=self._runs,
            episodes=self._episodes,
            steps=self._steps,
            attempts=self._attempts,
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
        observation_holder: dict[str, dict[str, Any]] = {}
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
            cognitive_session_factory=self._cognitive_session_factory(observation_holder),
            artifacts=self._artifacts_repo(),
        )

        if command.condition_index is not None:
            conditions = (resolved.conditions[command.condition_index],)
        else:
            conditions = resolved.conditions

        for condition in conditions:
            # ZGW-0103 R3: a declared exposure the cognitive path cannot
            # deliver is a configuration rejection, never a silent ignore.
            self._reject_unsupported_observation(condition)

        resolved_artifact = store_artifact(
            cas=self._cas,
            writer=writer,
            payload=ArtifactPayload(
                media_type="application/vnd.zugzwang.manifest-resolved+json",
                data=resolved.model_dump_json().encode("utf-8"),
            ),
        )
        # ZGW-0103 R4: the run is attributable to the exact code that executes
        # it (git SHA + dirty flag), pinned with the run row itself.
        code_pin = self._code_pin()
        last_run_id: str | None = None
        for condition in conditions:
            observation_holder["current"] = dict(condition.protocol.observation)
            cognitive_raw = cast("dict[str, Any] | None", condition.task.config.get("cognitive"))
            observation_holder["cognitive"] = dict(cognitive_raw) if cognitive_raw else {}
            exposure_ref = store_json_artifact(
                cas=self._cas,
                writer=writer,
                payload=self._exposure_manifest_payload(condition, code_pin),
                media_type="application/vnd.zugzwang.exposure-manifest+json",
            )
            run_id = await coordinator.start_and_run(
                resolved,
                condition,
                stop_event,
                run_extras={
                    **code_pin,
                    "exposure_manifest_artifact_id": exposure_ref.as_id(),
                },
            )
            self._runs.update_run(
                run_id, {"resolved_manifest_artifact_id": resolved_artifact.as_id()}
            )
            last_run_id = run_id
        await writer.flush()
        await writer.stop()
        close_backend = getattr(backend, "close", None)
        if callable(close_backend):
            closed = close_backend()
            if inspect.isawaitable(closed):
                await closed
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
        existing = self._runs.get_run(run_id)
        if existing is None:
            raise ValueError(f"run {run_id} not found")
        condition = resolved.condition_by_id(str(existing["condition_id"]))
        if condition is None:
            raise ValueError(f"condition for run {run_id} not found in manifest")
        backend = self._backend_for(condition)
        observation_holder: dict[str, dict[str, Any]] = {
            "current": dict(condition.protocol.observation)
        }
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
            cognitive_session_factory=self._cognitive_session_factory(observation_holder),
            artifacts=self._artifacts_repo(),
        )
        await coordinator.resume(run_id, resolved, stop_event)
        await writer.flush()
        await writer.stop()
        close_backend = getattr(backend, "close", None)
        if callable(close_backend):
            closed = close_backend()
            if inspect.isawaitable(closed):
                await closed
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
            episode_steps = self._steps.for_episode(episode["episode_id"])
            steps_committed += sum(1 for s in episode_steps if s["status"] == "COMMITTED")
            attempts += sum(len(self._attempts.for_step(s["step_id"])) for s in episode_steps)
        events = len(self._events.for_run(run_id))
        return RunSummary(
            run_id=row["run_id"],
            status=row["status"],
            condition_id=row["condition_id"],
            protocol_hash=row["protocol_hash"],
            declared_assistance=row["declared_assistance"],
            effective_assistance=row.get("effective_assistance"),
            assistance_violated=bool(row.get("assistance_violated", 0)),
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
                    timeout_seconds=float(backend_config.get("timeout_seconds", 60) or 60),
                    profile=str(backend_config.get("profile", "openai-chat-completions")),
                    allow_private_network=bool(backend_config.get("allow_private_network", False)),
                    image_input=bool(backend_config.get("image_input", False)),
                    reasoning_effort=(
                        str(backend_config["reasoning_effort"])
                        if backend_config.get("reasoning_effort")
                        else None
                    ),
                    default_max_output_tokens=(
                        int(backend_config["default_max_output_tokens"])
                        if backend_config.get("default_max_output_tokens")
                        else None
                    ),
                )
            if backend_id == "provider.antigravity_cli":
                from zgw_provider_antigravity_cli.adapter import AntigravityCliBackend

                return AntigravityCliBackend(
                    model=str(backend_config.get("model", "gemini-3.8-flash-low")),
                    executable=(
                        str(backend_config["executable"])
                        if backend_config.get("executable")
                        else None
                    ),
                    timeout_seconds=float(backend_config.get("timeout_seconds", 120) or 120),
                    reasoning_effort=(
                        str(backend_config["reasoning_effort"])
                        if backend_config.get("reasoning_effort")
                        else None
                    ),
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
    # Cognitive domain: the loop speaks json_commands; the fake answers the
    # opening round with an observe, then expands e2e4 by UCI (the loop
    # resolves it over the complete legal set), then finalizes it.
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
    cognitive_observe = _json.dumps({"command": "board_observe", "arguments": {}})
    cognitive_expand_e4 = _json.dumps({"command": "board_expand", "arguments": {"action": "e2e4"}})
    cognitive_finalize_e4 = _json.dumps(
        {"command": "board_finalize", "arguments": {"action": "e2e4"}}
    )
    return (
        FakeBackendRule(when={"fingerprint_contains": "fake-direct"}, output="inc"),
        FakeBackendRule(
            when={
                "fingerprint_contains": "cognitive-navigation",
                "call_index_modulo": [3, 0],
            },
            output=cognitive_observe,
        ),
        FakeBackendRule(
            when={
                "fingerprint_contains": "cognitive-navigation",
                "call_index_modulo": [3, 1],
            },
            output=cognitive_expand_e4,
        ),
        FakeBackendRule(
            when={
                "fingerprint_contains": "cognitive-navigation",
                "call_index_modulo": [3, 2],
            },
            output=cognitive_finalize_e4,
        ),
        FakeBackendRule(when={"fingerprint_contains": "chess-grounded"}, output="e2e4"),
        FakeBackendRule(when={"fingerprint_contains": "chess-repair"}, output="e2e4"),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-reason-then-ground-analyze"},
            output="Candidates:\ne2e4\ng1f3",
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-reason-then-ground-ground"},
            output="e2e4",
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-structured"}, output=structured_output
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-r6-candidates"},
            output='{"candidates":[{"move":"e2e4"},{"move":"e2e5"},{"move":"g1f3"}]}',
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-r6-judge"},
            output="1",
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-r6-refuter"},
            output="e7e5",
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-multi-agent:critical-scout"},
            output=_json.dumps(
                {
                    "critical_map": "opening development",
                    "hanging_pieces": [],
                    "tactical_ideas": ["control the center"],
                    "candidate_moves": ["e2e4", "g1f3"],
                    "confidence": 0.7,
                }
            ),
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-multi-agent:strategy-planner"},
            output=_json.dumps(
                {
                    "plan": "develop while contesting the center",
                    "candidate_moves": ["e2e4", "g1f3"],
                    "preferred_move": "e2e4",
                    "risks": [],
                }
            ),
        ),
        FakeBackendRule(
            when={"fingerprint_contains": "chess-multi-agent:final-reviewer"},
            output=_json.dumps(
                {
                    "move": "e2e4",
                    "review": "the move is consistent with the position",
                    "critical_risks_addressed": ["development"],
                    "confidence": 0.8,
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 0,
                "fingerprint_contains": "chess-legal-tree-memory:position-mapper",
            },
            output=_json.dumps(
                {
                    "critical_map": "opening development",
                    "hanging_pieces": [],
                    "tactical_ideas": ["control the center"],
                    "candidate_moves": ["e2e4"],
                    "illegal_probes": ["e2e5"],
                    "confidence": 0.8,
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 0,
                "fingerprint_contains": "chess-single-agent-tree:single-agent",
            },
            output=_json.dumps(
                {
                    "critical_map": "opening development",
                    "hanging_pieces": [],
                    "tactical_ideas": ["control the center"],
                    "candidate_moves": ["e2e4"],
                    "illegal_probes": ["e2e5"],
                    "variants": [
                        {
                            "root_move": "e2e4",
                            "reply_move": "e7e5",
                            "illegal_reply_probes": ["e2e6"],
                            "assessment": "central contest",
                            "risks": [],
                        }
                    ],
                    "move": "e2e4",
                    "analysis": "legal central move",
                    "confidence": 0.9,
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 1,
                "fingerprint_contains": "chess-legal-tree-memory:variant-analyst",
            },
            output=_json.dumps(
                {
                    "variants": [
                        {
                            "root_move": "e2e4",
                            "reply_move": "e7e5",
                            "assessment": "central contest",
                            "risks": [],
                        }
                    ],
                    "preferred_root": "e2e4",
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 2,
                "fingerprint_contains": "chess-legal-tree-memory:final-reviewer",
            },
            output=_json.dumps(
                {
                    "move": "e2e4",
                    "review": "legal opening move",
                    "critical_risks_addressed": ["king safety"],
                    "confidence": 0.9,
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 3,
                "fingerprint_contains": "chess-legal-tree-memory:position-mapper",
            },
            output=_json.dumps(
                {
                    "critical_map": "develop the knight",
                    "hanging_pieces": [],
                    "tactical_ideas": ["develop"],
                    "candidate_moves": ["g1f3"],
                    "illegal_probes": [],
                    "confidence": 0.8,
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 4,
                "fingerprint_contains": "chess-legal-tree-memory:variant-analyst",
            },
            output=_json.dumps(
                {
                    "variants": [
                        {
                            "root_move": "g1f3",
                            "reply_move": "g8f6",
                            "assessment": "develop both knights",
                            "risks": [],
                        }
                    ],
                    "preferred_root": "g1f3",
                }
            ),
        ),
        FakeBackendRule(
            when={
                "call_index": 5,
                "fingerprint_contains": "chess-legal-tree-memory:final-reviewer",
            },
            output=_json.dumps(
                {
                    "move": "g1f3",
                    "review": "legal development move",
                    "critical_risks_addressed": ["development"],
                    "confidence": 0.9,
                }
            ),
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
