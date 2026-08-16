"""zugzwang / zgw — Zugzwang Research Kernel CLI."""

from __future__ import annotations

import asyncio
import contextvars
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from zugzwang_core.domain.manifests import ManifestPatch
from zugzwang_core.spec.json_schema import generate_json_schemas
from zugzwang_runtime.application import (
    DoctorService,
    PlanExperimentService,
    ValidateManifestService,
)
from zugzwang_runtime.application.commands import (
    PlanExperimentCommand,
    StartRunCommand,
    ValidateManifestCommand,
)
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.workspace import Workspace

from .output import ExitCode, exit_code_for, print_diagnostic
from .rendering import print_result

app = typer.Typer(
    name="zugzwang",
    help="Zugzwang Research Kernel — attribution-first local experimentation.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)

experiment_app = typer.Typer(help="Manifest validation and planning.", no_args_is_help=True)
app.add_typer(experiment_app, name="experiment")

plugins_app = typer.Typer(help="Plugin discovery.", no_args_is_help=True)
app.add_typer(plugins_app, name="plugins")

_OUTPUT = contextvars.ContextVar("zgw_output", default="human")
_QUIET = contextvars.ContextVar("zgw_quiet", default=False)

_OutputOption = Annotated[str, typer.Option("--output", "-o", help="human|json|jsonl")]
_QuietOption = Annotated[bool, typer.Option("--quiet", help="suppress progress output")]


def _set_globals(output: str, quiet: bool) -> None:
    if output not in ("human", "json", "jsonl"):
        raise typer.BadParameter("--output must be one of: human, json, jsonl")
    _OUTPUT.set(output)
    _QUIET.set(quiet)


def _fmt() -> str:
    return _OUTPUT.get()


@app.command()
def init(
    directory: Annotated[
        Path | None,
        typer.Argument(help="workspace root (default: current directory)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Initialize a local .zugzwang workspace."""
    _set_globals(output, quiet)
    root = (directory or Path.cwd()).resolve()
    workspace = Workspace.from_root(root)
    created = workspace.ensure_layout()
    result = {"workspace_root": str(root), "created": [str(c) for c in created]}
    print_result(result, _fmt())


@app.command()
def doctor(
    directory: Annotated[
        Path | None,
        typer.Option("--directory", "-d", help="check from this directory"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Validate workspace, database, plugins and environment."""
    _set_globals(output, quiet)
    result = DoctorService().run(directory)
    print_result(result, _fmt())
    if result.status == "error":
        raise typer.Exit(ExitCode.CONFIGURATION)


@app.command()
def schema(
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="output directory for JSON Schemas"),
    ] = Path("schemas"),
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Regenerate versioned JSON Schemas from the strict models."""
    _set_globals(output, quiet)
    schemas = generate_json_schemas()
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, schema_json in schemas.items():
        target = out / f"{name}.zgw.dev-v1alpha1.schema.json"
        target.write_text(
            json.dumps(schema_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written.append(str(target))
    print_result({"schemas": written}, _fmt())


@experiment_app.command("validate")
def experiment_validate(
    manifest: Annotated[Path, typer.Argument(help="manifest .yaml/.yml/.json")],
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Validate a manifest strictly, with actionable diagnostics."""
    _set_globals(output, quiet)
    result = ValidateManifestService().validate(ValidateManifestCommand(manifest_path=manifest))
    print_result(result, _fmt())


@experiment_app.command("plan")
def experiment_plan(
    manifest: Annotated[Path, typer.Argument(help="manifest .yaml/.yml/.json")],
    set_patch: Annotated[
        list[str] | None,
        typer.Option("--set", help="patch, e.g. /spec/budget/max_usd=5 (repeatable)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Resolve and plan an experiment without executing it."""
    _set_globals(output, quiet)
    patches = tuple(_parse_patches(set_patch or []))
    result = PlanExperimentService(PluginRegistry()).plan(
        PlanExperimentCommand(manifest_path=manifest, patches=patches)
    )
    print_result(result, _fmt())


@app.command()
def run(
    manifest: Annotated[Path, typer.Argument(help="manifest .yaml/.yml/.json")],
    set_patch: Annotated[
        list[str] | None,
        typer.Option("--set", help="patch, e.g. /spec/budget/max_usd=5 (repeatable)"),
    ] = None,
    condition: Annotated[
        int | None,
        typer.Option("--condition", help="run only this condition index"),
    ] = None,
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Run an experiment durably (SQLite + CAS; fake backend offline by default)."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    patches = tuple(_parse_patches(set_patch or []))
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    stop_event = asyncio.Event()
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            services.start(
                StartRunCommand(
                    manifest_path=manifest,
                    patches=patches,
                    condition_index=condition,
                ),
                stop_event,
            )
        )
    except KeyboardInterrupt:
        stop_event.set()
        print_diagnostic(KeyboardInterrupt())
        raise typer.Exit(ExitCode.INTERRUPTED) from None
    finally:
        loop.close()
    print_result(result, _fmt())


@app.command()
def resume(
    run_id: Annotated[str, typer.Argument(help="run id to resume")],
    manifest: Annotated[Path, typer.Argument(help="original manifest .yaml/.yml/.json")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Resume an interrupted run from its first non-committed step."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    stop_event = asyncio.Event()
    result = asyncio.run(services.resume(run_id, manifest, stop_event))
    print_result(result, _fmt())


@app.command()
def cancel(
    run_id: Annotated[str, typer.Argument(help="run id to cancel")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Cancel a non-terminal run."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    print_result(services.cancel(run_id), _fmt())


runs_app = typer.Typer(help="Run queries.", no_args_is_help=True)
app.add_typer(runs_app, name="runs")


@runs_app.command("list")
def runs_list(
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """List runs in this workspace."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    print_result([s.model_dump() for s in services.list_runs()], _fmt())


@runs_app.command("show")
def runs_show(
    run_id: Annotated[str, typer.Argument(help="run id")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Show one run's projection summary."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    print_result(services.summary(run_id), _fmt())


db_app = typer.Typer(help="Operational database management.", no_args_is_help=True)
app.add_typer(db_app, name="db")


@db_app.command("status")
def db_status(
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Show migration revision and database health."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    print_result(services.db_status(), _fmt())


@db_app.command("upgrade")
def db_upgrade(
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Run pending Alembic migrations."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    print_result(services.db_upgrade(), _fmt())


@app.command()
def evaluate(
    run_id: Annotated[str, typer.Argument(help="run id to evaluate post-hoc")],
    evaluator: Annotated[
        str,
        typer.Option("--evaluator", help="evaluator plugin id (default: evaluator.stockfish)"),
    ] = "evaluator.stockfish",
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Run a post-hoc evaluator over a finished run (never alters the run)."""
    _set_globals(output, quiet)
    from zgw_eval_stockfish.evaluator import StockfishEvaluator
    from zgw_eval_stockfish.uci import FakeUciEngine

    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.application.evaluation import EvaluateRunService

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    evaluator_obj = StockfishEvaluator(
        FakeUciEngine(),
        binary_metadata={"binary": "fake-engine", "note": "offline fake UCI; no real engine"},
    )
    summary = asyncio.run(
        EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=__import__(
                "zugzwang_runtime.persistence.repositories",
                fromlist=["MetricObservationRepository"],
            ).MetricObservationRepository(services.database_engine),
            cas=services.cas,
        ).evaluate(run_id, evaluator_obj, evaluator_id=evaluator)
    )
    print_result(summary, _fmt())


@app.command()
def report(
    run_id: Annotated[str, typer.Argument(help="run id to report")],
    markdown: Annotated[
        Path | None,
        typer.Option("--markdown", help="write a Markdown report to this path"),
    ] = None,
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Produce an honest run report (terminal, JSON or Markdown)."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.application.evaluation import ReportRunService
    from zugzwang_runtime.persistence.repositories import MetricObservationRepository

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    report_service = ReportRunService(
        runs=services.runs,
        episodes=services.episodes,
        steps=services.steps,
        metrics=MetricObservationRepository(services.database_engine),
        events=services.events,
    )
    data = report_service.report(run_id)
    if markdown is not None:
        markdown.write_text(report_service.to_markdown(data), encoding="utf-8")
    if output == "json":
        print_result(data, "json")
    else:
        print_result(report_service.to_markdown(data), "human")


@app.command()
def export(
    run_id: Annotated[str, typer.Argument(help="run id to export")],
    output_dir: Annotated[Path, typer.Option("--output", "-o", help="bundle directory")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Export a self-contained run bundle with checksums."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.bundles import ExportRunBundleService
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.persistence.repositories import ArtifactRepository

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    exporter = ExportRunBundleService(
        runs=services.runs,
        episodes=services.episodes,
        steps=services.steps,
        metrics=__import__(
            "zugzwang_runtime.persistence.repositories", fromlist=["MetricObservationRepository"]
        ).MetricObservationRepository(services.database_engine),
        events=services.events,
        artifacts=ArtifactRepository(services.database_engine),
        cas=services.cas,
        run_dir=services.workspace.run_dir(run_id),
    )
    bundle_dir = exporter.export(run_id, output_dir)
    print_result({"bundle": str(bundle_dir)}, _fmt())


@app.command()
def import_bundle(
    bundle: Annotated[Path, typer.Argument(help="bundle directory to import")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Import a bundle after validating schema and checksums."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.bundles import ImportRunBundleService
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.persistence.repositories import ArtifactRepository

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    importer = ImportRunBundleService(
        cas=services.cas,
        artifacts=ArtifactRepository(services.database_engine),
    )
    result = importer.import_bundle(bundle)
    print_result(result, _fmt())


@app.command()
def gc(
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="actually delete orphans")] = False,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Garbage-collect unreferenced CAS objects (--yes to delete)."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.bundles import GarbageCollector
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.persistence.repositories import ArtifactRepository

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    collector = GarbageCollector(
        cas=services.cas,
        artifacts=ArtifactRepository(services.database_engine),
    )
    result = collector.collect(dry_run=not yes)
    print_result(result, _fmt())


@app.command()
def replay(
    run_id: Annotated[str, typer.Argument(help="run id to replay offline")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="workspace root (default: discovered from cwd)"),
    ] = None,
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Replay stored parsing and transitions without any provider call."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.persistence.repositories import (
        EpisodeRepository,
        StepRepository,
    )

    resolved_workspace = _resolve_workspace(workspace)
    services = DurableRunServices(resolved_workspace, PluginRegistry())
    rows = EpisodeRepository(services.database_engine).for_run(run_id)
    steps = StepRepository(services.database_engine)
    result: list[dict[str, Any]] = []
    for episode in rows:
        committed = [
            s for s in steps.for_episode(episode["episode_id"]) if s["status"] == "COMMITTED"
        ]
        actions: list[str] = []
        for committed_step in committed:
            action_json: dict[str, Any] = dict(committed_step.get("action_json") or {})
            action = action_json.get("action")
            if isinstance(action, str):
                actions.append(action)
        result.append(
            {
                "episode_id": episode["episode_id"],
                "outcome": episode.get("outcome"),
                "replayed_steps": len(committed),
                "actions": actions,
            }
        )
    print_result({"run_id": run_id, "episodes": result, "offline": True}, _fmt())


@app.command()
def sbom(
    out: Annotated[Path, typer.Option("--out", "-o", help="output CycloneDX JSON path")] = Path(
        "sbom.cyclonedx.json"
    ),
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """Export a CycloneDX SBOM from the locked dependency set."""
    _set_globals(output, quiet)
    from zugzwang_runtime.application.sbom import write_sbom

    written = write_sbom(Path.cwd(), out)
    print_result({"sbom": str(written)}, _fmt())


def _resolve_workspace(workspace: Path | None) -> Workspace:
    if workspace is not None:
        return Workspace.from_root(workspace)
    from zugzwang_core.domain.errors import ConfigurationError

    try:
        return Workspace.discover()
    except ConfigurationError as exc:
        raise typer.BadParameter(
            "no .zugzwang workspace found; run 'zugzwang init' or pass --workspace"
        ) from exc


@plugins_app.command("list")
def plugins_list(
    output: _OutputOption = "human",
    quiet: _QuietOption = False,
) -> None:
    """List discovered plugins with descriptors."""
    _set_globals(output, quiet)
    registry = PluginRegistry()
    result = {
        "plugins": [d.model_dump() for d in registry.descriptors()],
        "errors": list(registry.errors()),
    }
    print_result(result, _fmt())


def _parse_patches(raw: list[str]) -> tuple[ManifestPatch, ...]:
    patches: list[ManifestPatch] = []
    for item in raw:
        if "=" not in item:
            raise typer.BadParameter(f"patch must be PATH=VALUE, got {item!r}")
        path, raw_value = item.split("=", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        patches.append(ManifestPatch(path=path, value=value))
    return tuple(patches)


def _run_cli() -> None:
    try:
        app()
    except typer.Exit:
        raise
    except Exception as exc:
        print_diagnostic(exc)
        sys.exit(int(exit_code_for(exc)))


def run_cli() -> None:
    """Console-script entry point with stable diagnostics."""
    _run_cli()


if __name__ == "__main__":
    _run_cli()
