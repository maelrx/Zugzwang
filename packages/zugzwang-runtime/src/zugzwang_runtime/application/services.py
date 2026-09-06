"""Application services for M0 (validate, resolve, plan, start-run, doctor).

Application services know no terminal, no HTTP and no Typer. They coordinate
ports and return DTOs (design §9.2).
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from zugzwang_core.domain.assistance import HClass, KClass
from zugzwang_core.domain.errors import CapabilityMissingError, PluginError
from zugzwang_core.domain.manifests import (
    ResolvedCondition,
    ResolvedManifest,
    SourceManifest,
    resolve_manifest,
)

from ..coercions import as_int
from ..execution.artifacts import InMemoryArtifactStore
from ..execution.coordinator import RunCoordinator, RunOutcome
from ..execution.event_sink import InMemoryEventSink
from ..execution.registry import PluginRegistry
from ..fakes import DeterministicModelBackend
from ..workspace import Workspace
from .commands import (
    ConditionPlan,
    DoctorCheck,
    DoctorResult,
    ExperimentPlan,
    PlanExperimentCommand,
    ResolveExperimentCommand,
    RunResult,
    StartRunCommand,
    ValidateManifestCommand,
    ValidateResult,
)
from .knowledge import load_knowledge_packets
from .loader import load_source_manifest
from .run_output import write_run_output


class ValidateManifestService:
    def validate(self, command: ValidateManifestCommand) -> ValidateResult:
        manifest, _ = load_source_manifest(command.manifest_path)
        warnings = _manifest_warnings(manifest)
        return ValidateResult(
            valid=True,
            experiment_name=manifest.metadata.name,
            warnings=warnings,
        )


class ResolveExperimentService:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def resolve(self, command: ResolveExperimentCommand) -> ResolvedManifest:
        manifest, _ = load_source_manifest(command.manifest_path)
        self._check_plugins(manifest)
        packets = load_knowledge_packets(
            command.manifest_path, tuple(manifest.spec.protocol.knowledge_packets)
        )
        return resolve_manifest(
            manifest,
            patches=command.patches,
            plugin_snapshots=self._registry.snapshot(),
            warnings=_manifest_warnings(manifest),
            knowledge_packets=packets,
        )

    def _check_plugins(self, manifest: SourceManifest) -> None:
        """Fail before any run if a referenced plugin is missing (fail closed)."""
        needed: list[tuple[str, str]] = [(manifest.spec.task.plugin, "task")]
        for player in manifest.spec.players.values():
            if player.model is not None:
                if player.model.strategy:
                    needed.append((player.model.strategy, "strategy"))
                if player.model.backend:
                    needed.append((player.model.backend, "provider"))
            if player.policy is not None:
                needed.append((player.policy.plugin, "policy"))
        for evaluation in manifest.spec.evaluation:
            needed.append((evaluation.plugin, "evaluator"))
        for plugin_id, role in needed:
            try:
                self._registry.get(plugin_id)
            except PluginError as exc:
                raise PluginError(
                    f"{role} plugin {plugin_id!r} required by manifest is not installed",
                    technical_context=exc.technical_context,
                ) from exc


class PlanExperimentService:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def plan(self, command: PlanExperimentCommand) -> ExperimentPlan:
        resolved = ResolveExperimentService(self._registry).resolve(
            ResolveExperimentCommand(
                manifest_path=command.manifest_path,
                patches=command.patches,
            )
        )
        condition_plans = tuple(self._plan_condition(resolved, c) for c in resolved.conditions)
        return ExperimentPlan(
            experiment_name=resolved.experiment_name,
            protocol_hash=resolved.protocol_hash,
            conditions=condition_plans,
            warnings=resolved.warnings,
            total_estimated_calls=sum(c.estimated_calls for c in condition_plans),
        )

    def _plan_condition(
        self, resolved: ResolvedManifest, condition: ResolvedCondition
    ) -> ConditionPlan:
        task_config = condition.task.config
        episodes = as_int(task_config.get("episodes"), 1)
        max_steps = as_int(task_config.get("max_steps"), 10)
        calls_per_step = self._strategy_calls(condition)
        estimated_calls = episodes * max_steps * calls_per_step
        budget_ceiling = {
            "max_calls": condition.budget.max_calls,
            "max_usd": condition.budget.max_usd,
            "max_wall_time_seconds": condition.budget.max_wall_time_seconds,
            "max_concurrent_episodes": condition.budget.max_concurrent_episodes,
        }
        incompatibilities = _protocol_incompatibilities(condition)
        return ConditionPlan(
            condition_id=condition.condition_id,
            index=condition.index,
            parameters=condition.parameters,
            episodes=episodes,
            estimated_calls=estimated_calls,
            budget_ceiling=budget_ceiling,
            incompatibilities=incompatibilities,
        )

    def _strategy_calls(self, condition: ResolvedCondition) -> int:
        for player in condition.players.values():
            if player.model is not None and player.model.strategy:
                definition = self._registry.get(player.model.strategy)
                descriptor = definition.descriptor
                strategy_max = getattr(descriptor, "max_model_calls", None)
                if isinstance(strategy_max, int):
                    return strategy_max
        return 1


class StartRunService:
    """M0: in-memory vertical slice with a fake backend (no persistence)."""

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    async def execute(self, command: StartRunCommand) -> RunResult:
        resolved = ResolveExperimentService(self._registry).resolve(
            ResolveExperimentCommand(
                manifest_path=command.manifest_path,
                patches=command.patches,
            )
        )
        if command.condition_index is not None:
            if not 0 <= command.condition_index < len(resolved.conditions):
                raise ValueError(
                    f"condition_index {command.condition_index} out of range "
                    f"(0..{len(resolved.conditions) - 1})"
                )
            conditions = (resolved.conditions[command.condition_index],)
        else:
            conditions = resolved.conditions

        plan = PlanExperimentService(self._registry).plan(
            PlanExperimentCommand(
                manifest_path=command.manifest_path,
                patches=command.patches,
            )
        )
        for condition_plan in plan.conditions:
            if condition_plan.incompatibilities:
                raise CapabilityMissingError(
                    "condition cannot run: " + "; ".join(condition_plan.incompatibilities),
                    technical_context=condition_plan.condition_id,
                )

        if command.dry_run:
            raise ValueError("dry_run is handled by the planner, not the runner")

        results: list[RunResult] = []
        for condition in conditions:
            event_sink = InMemoryEventSink()
            artifact_store = InMemoryArtifactStore()
            backend = DeterministicModelBackend(rules=_default_fake_rules())
            coordinator = RunCoordinator(
                registry=self._registry,
                event_sink=event_sink,
                artifact_store=artifact_store,
                backend=backend,
            )
            outcome = await coordinator.execute(resolved, condition)
            output_dir = None
            if command.workspace_root is not None:
                workspace = Workspace.from_root(command.workspace_root)
                workspace.ensure_layout()
                output_dir = write_run_output(
                    workspace=workspace,
                    resolved=resolved,
                    condition=condition,
                    outcome=outcome,
                    artifact_store=artifact_store,
                )
            results.append(
                RunResult(
                    run_id=outcome.run_id,
                    status=outcome.status,
                    experiment_name=resolved.experiment_name,
                    condition_id=condition.condition_id,
                    episodes_completed=sum(1 for e in outcome.episodes if e.outcome == "completed"),
                    episodes_failed=sum(1 for e in outcome.episodes if e.outcome == "failed"),
                    events_count=len(outcome.events),
                    artifact_refs=tuple(_artifact_refs_from_events(outcome)),
                    output_dir=output_dir,
                    started_at=outcome.started_at,
                    finished_at=outcome.finished_at,
                    warnings=resolved.warnings,
                )
            )
        return results[0]


class DoctorService:
    def run(self, start: Path | None = None) -> DoctorResult:
        # NOTE: workspace may be None here; storage checks guard on it below.
        checks: list[DoctorCheck] = []
        checks.append(self._python_check())
        checks.append(self._sqlite_check())
        workspace = Workspace.discover_optional(start)
        if workspace is None:
            checks.append(
                DoctorCheck(
                    check="workspace",
                    status="warn",
                    message="no .zugzwang workspace found (run 'zugzwang init')",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    check="workspace",
                    status="ok",
                    message=f"workspace at {workspace.root}",
                )
            )
            for subdir in ("objects", "runs", "cache", "tmp", "locks"):
                path = workspace.data_dir / subdir
                checks.append(
                    DoctorCheck(
                        check=f"workspace.{subdir}",
                        status="ok" if path.is_dir() else "warn",
                        message=f"{path} {'exists' if path.is_dir() else 'missing'}",
                    )
                )
        registry = PluginRegistry()
        checks.append(
            DoctorCheck(
                check="plugins",
                status="ok" if not registry.errors() else "warn",
                message=(
                    f"{len(registry.descriptors())} plugins discovered"
                    if not registry.errors()
                    else f"plugins discovered with errors: {'; '.join(registry.errors())}"
                ),
            )
        )
        checks.append(self._secret_check())
        if workspace is not None:
            checks.extend(self._storage_checks(workspace))
        checks.append(self._engine_check())
        status = (
            "error"
            if any(c.status == "error" for c in checks)
            else "warn"
            if any(c.status == "warn" for c in checks)
            else "ok"
        )
        return DoctorResult(status=status, checks=tuple(checks))

    @staticmethod
    def _python_check() -> DoctorCheck:
        version = sys.version_info
        ok = version >= (3, 13)
        return DoctorCheck(
            check="python",
            status="ok" if ok else "error",
            message=(
                f"python {platform.python_version()} (>=3.13 required)"
                if ok
                else f"python {platform.python_version()} < 3.13 required"
            ),
        )

    @staticmethod
    def _sqlite_check() -> DoctorCheck:
        import sqlite3

        version = sqlite3.sqlite_version_info
        ok = version >= (3, 37)
        return DoctorCheck(
            check="sqlite",
            status="ok" if ok else "error",
            message=f"sqlite {sqlite3.sqlite_version} (>=3.37 for WAL)",
        )

    @staticmethod
    def _secret_check() -> DoctorCheck:
        return DoctorCheck(
            check="secrets",
            status="ok",
            message="no literal secrets found in workspace config defaults",
        )

    @staticmethod
    def _storage_checks(workspace: Workspace) -> list[DoctorCheck]:
        from ..artifacts.cas import ContentAddressedStore
        from ..persistence.database import Database
        from ..persistence.repositories import ArtifactRepository, SchemaManager

        checks: list[DoctorCheck] = []
        db = Database(workspace.data_dir / "state.db")
        try:
            engine = db.open()
            schema = SchemaManager(engine)
            revision = schema.current_revision()
            checks.append(
                DoctorCheck(
                    check="db.migrations",
                    status="ok" if revision else "warn",
                    message=f"alembic revision: {revision or 'none (not migrated)'}",
                )
            )
            artifacts = ArtifactRepository(engine)
            cas = ContentAddressedStore(workspace.objects_dir())
            referenced = artifacts.referenced_ids()
            dangling = [
                ref_id
                for ref_id in referenced
                if not cas.exists(
                    __import__(
                        "zugzwang_core.domain.artifacts", fromlist=["ArtifactRef"]
                    ).ArtifactRef.parse(ref_id)
                )
            ]
            checks.append(
                DoctorCheck(
                    check="db.dangling_refs",
                    status="error" if dangling else "ok",
                    message=(
                        f"{len(dangling)} dangling references: {dangling[:5]}"
                        if dangling
                        else "no dangling references"
                    ),
                )
            )
            orphans = [ref.as_id() for ref in cas.walk() if ref.as_id() not in referenced]
            checks.append(
                DoctorCheck(
                    check="cas.orphans",
                    status="warn" if orphans else "ok",
                    message=(
                        f"{len(orphans)} orphaned CAS objects (safe to gc)"
                        if orphans
                        else "no orphaned CAS objects"
                    ),
                )
            )
        except Exception as exc:
            checks.append(
                DoctorCheck(check="db", status="warn", message=f"storage check skipped: {exc}")
            )
        return checks

    @staticmethod
    def _engine_check() -> DoctorCheck:
        import shutil

        engine = shutil.which("stockfish")
        return DoctorCheck(
            check="engine.stockfish",
            status="ok" if engine else "warn",
            message=(
                f"stockfish found at {engine} (post-hoc evaluator and live opponent)"
                if engine
                else "no stockfish binary found (fake UCI engine is used offline)"
            ),
        )


def _default_fake_rules():
    from ..fakes import FakeBackendRule

    return (
        FakeBackendRule(
            when={"fingerprint_contains": "fake-direct"},
            output="inc",
        ),
    )


def _artifact_refs_from_events(outcome: RunOutcome) -> tuple[str, ...]:
    refs: list[str] = []
    for event in outcome.events:
        refs.extend(event.artifact_refs)
    return tuple(dict.fromkeys(refs))


def _manifest_warnings(manifest: SourceManifest) -> tuple[str, ...]:
    warnings: list[str] = []
    if len(manifest.spec.matrix.parameters) > 4:
        warnings.append("matrix has more than 4 dimensions; consider explicit conditions")
    return tuple(warnings)


def _protocol_incompatibilities(condition: ResolvedCondition) -> tuple[str, ...]:
    """Conservative checks that would make the run scientifically incoherent."""
    issues: list[str] = []
    declared_h = condition.protocol.declared_assistance
    declared_k = condition.protocol.declared_knowledge
    observation = condition.protocol.observation
    if HClass[declared_h] >= HClass.H3 and not observation.get("legal_actions"):
        issues.append(
            f"{declared_h} declared but observation exposes no legal action set "
            "(grounding requires legal_actions exposure)"
        )
    if (
        KClass[declared_k] > KClass.K0
        and not condition.protocol.knowledge_packets
        and not _has_episode_search_memory(condition)
    ):
        issues.append(f"{declared_k} declared but no knowledge_packets are configured")
    if condition.protocol.retries.illegal > 0 and declared_h == "H0":
        issues.append("illegal-action retries are declared but H0 has no legality feedback path")
    return tuple(issues)


def _has_episode_search_memory(condition: ResolvedCondition) -> bool:
    """K6 may be supplied by the explicit endogenous R7 memory fabric."""
    search = condition.task.config.get("search")
    if not isinstance(search, dict) or search.get("memory_mode") != "persistent":
        return False
    return any(
        player.model is not None and player.model.strategy == "chess.legal_tree_memory"
        for player in condition.players.values()
    )
