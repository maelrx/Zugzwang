"""Application commands and results (design §9.2 and §32).

Commands are typed DTOs; services return DTOs. The CLI renders these; a future
API would call the same objects (ADR-029).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zugzwang_core.domain.manifests import ManifestPatch


class ValidateManifestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_path: Path


class ResolveExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_path: Path
    patches: tuple[ManifestPatch, ...] = ()


class PlanExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_path: Path
    patches: tuple[ManifestPatch, ...] = ()


class StartRunCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_path: Path
    patches: tuple[ManifestPatch, ...] = ()
    condition_index: int | None = None
    dry_run: bool = False
    workspace_root: Path | None = None


class ValidateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    experiment_name: str
    warnings: tuple[str, ...] = ()


class ConditionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_id: str
    index: int
    parameters: dict[str, Any]
    episodes: int
    estimated_calls: int
    budget_ceiling: dict[str, Any]
    incompatibilities: tuple[str, ...] = ()


class ExperimentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_name: str
    protocol_hash: str
    conditions: tuple[ConditionPlan, ...]
    warnings: tuple[str, ...] = ()
    total_estimated_calls: int


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    status: str
    experiment_name: str
    condition_id: str
    episodes_completed: int
    episodes_failed: int
    events_count: int
    artifact_refs: tuple[str, ...] = ()
    output_dir: str | None = None
    started_at: str
    finished_at: str
    warnings: tuple[str, ...] = ()


class DoctorCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check: str
    status: str = Field(pattern=r"^(ok|warn|error)$")
    message: str


class DoctorResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(pattern=r"^(ok|warn|error)$")
    checks: tuple[DoctorCheck, ...]


class InitResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_root: str
    created: tuple[str, ...]
