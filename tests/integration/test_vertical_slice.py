from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang_runtime.application import (
    PlanExperimentService,
    ResolveExperimentService,
    StartRunService,
    ValidateManifestService,
)
from zugzwang_runtime.application.commands import (
    PlanExperimentCommand,
    ResolveExperimentCommand,
    StartRunCommand,
    ValidateManifestCommand,
)
from zugzwang_runtime.execution import PluginRegistry

MANIFEST = Path(__file__).resolve().parents[2] / "experiments" / "fake-smoke.yaml"


@pytest.fixture(scope="module")
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.mark.integration
def test_validate(registry: PluginRegistry) -> None:
    result = ValidateManifestService().validate(ValidateManifestCommand(manifest_path=MANIFEST))
    assert result.valid
    assert result.experiment_name == "fake-smoke"


@pytest.mark.integration
def test_resolve_produces_snapshots(registry: PluginRegistry) -> None:
    resolved = ResolveExperimentService(registry).resolve(
        ResolveExperimentCommand(manifest_path=MANIFEST)
    )
    assert resolved.protocol_hash
    assert len(resolved.conditions) == 1
    assert resolved.plugin_snapshots


@pytest.mark.integration
def test_plan_estimates(registry: PluginRegistry) -> None:
    plan = PlanExperimentService(registry).plan(PlanExperimentCommand(manifest_path=MANIFEST))
    assert plan.total_estimated_calls == 12
    assert plan.conditions[0].episodes == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vertical_slice_runs_offline(registry: PluginRegistry, tmp_path) -> None:
    result = await StartRunService(registry).execute(
        StartRunCommand(manifest_path=MANIFEST, workspace_root=tmp_path)
    )
    assert result.status == "COMPLETED"
    assert result.episodes_completed == 2
    assert result.events_count > 0
    assert result.output_dir is not None

    run_dir = tmp_path / ".zugzwang" / "runs" / result.run_id
    assert (run_dir / "manifest.resolved.json").exists()
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "checksums.sha256").exists()
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    event_types = [line.split('"event_type":"')[1].split('"')[0] for line in events]
    assert "run.started" in event_types
    assert "run.finalized" in event_types
    assert "step.committed" in event_types


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vertical_slice_deterministic_protocol_hash(registry: PluginRegistry) -> None:
    first = await StartRunService(registry).execute(StartRunCommand(manifest_path=MANIFEST))
    second = await StartRunService(registry).execute(StartRunCommand(manifest_path=MANIFEST))
    resolved = ResolveExperimentService(registry).resolve(
        ResolveExperimentCommand(manifest_path=MANIFEST)
    )
    assert first.status == second.status
    assert first.episodes_completed == second.episodes_completed
    assert resolved.protocol_hash == resolved.protocol_hash
