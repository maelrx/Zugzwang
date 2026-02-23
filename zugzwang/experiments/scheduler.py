from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal, Sequence

from zugzwang.infra.ids import timestamp_utc


BatchStatus = Literal["queued", "running", "completed", "failed", "canceled", "dry_run"]
BatchStepStatus = Literal["pending", "running", "completed", "failed", "canceled", "skipped", "dry_run"]
RunMode = Literal["run", "play"]


class SchedulerError(ValueError):
    pass


@dataclass
class BatchStepDefinition:
    step_id: str
    config_path: str
    mode: RunMode = "run"
    model_profile: str | None = None
    overrides: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class BatchStepState:
    step_id: str
    config_path: str
    mode: RunMode
    model_profile: str | None
    overrides: list[str]
    depends_on: list[str]
    status: BatchStepStatus = "pending"
    message: str | None = None
    job_id: str | None = None
    run_id: str | None = None
    run_dir: str | None = None
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    preview: dict[str, Any] | None = None


@dataclass
class BatchState:
    batch_id: str
    status: BatchStatus
    fail_fast: bool
    dry_run: bool
    created_at_utc: str
    updated_at_utc: str
    steps: list[BatchStepState]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_step_definitions(raw_steps: Sequence[dict[str, Any]]) -> list[BatchStepDefinition]:
    if not raw_steps:
        raise SchedulerError("batch requires at least one step")

    steps: list[BatchStepDefinition] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            raise SchedulerError(f"step {index} must be an object")

        step_id = _as_step_id(raw.get("step_id"), default=f"step_{index}")
        if step_id in seen_ids:
            raise SchedulerError(f"duplicate step_id: {step_id}")
        seen_ids.add(step_id)

        config_path = str(raw.get("config_path", "")).strip()
        if not config_path:
            raise SchedulerError(f"step {step_id} is missing config_path")

        mode_raw = str(raw.get("mode", "run")).strip().lower()
        mode: RunMode
        if mode_raw in {"run", "play"}:
            mode = mode_raw
        else:
            raise SchedulerError(f"step {step_id} has invalid mode: {mode_raw}")

        model_profile = _as_optional_str(raw.get("model_profile"))
        overrides = _normalize_str_list(raw.get("overrides"), field_name=f"step {step_id}.overrides")
        depends_on = _normalize_str_list(raw.get("depends_on"), field_name=f"step {step_id}.depends_on")

        steps.append(
            BatchStepDefinition(
                step_id=step_id,
                config_path=config_path,
                mode=mode,
                model_profile=model_profile,
                overrides=overrides,
                depends_on=depends_on,
            )
        )

    _validate_no_cycles(steps)
    return steps


def build_batch_state(
    *,
    batch_id: str,
    definitions: Sequence[BatchStepDefinition],
    fail_fast: bool,
    dry_run: bool,
    previews: dict[str, dict[str, Any]] | None = None,
) -> BatchState:
    now = timestamp_utc()
    preview_map = previews or {}
    steps: list[BatchStepState] = []
    for definition in definitions:
        status: BatchStepStatus = "dry_run" if dry_run else "pending"
        message = "validated (dry-run)" if dry_run else None
        steps.append(
            BatchStepState(
                step_id=definition.step_id,
                config_path=definition.config_path,
                mode=definition.mode,
                model_profile=definition.model_profile,
                overrides=list(definition.overrides),
                depends_on=list(definition.depends_on),
                status=status,
                message=message,
                preview=preview_map.get(definition.step_id),
            )
        )

    batch_status: BatchStatus = "dry_run" if dry_run else "queued"
    return BatchState(
        batch_id=batch_id,
        status=batch_status,
        fail_fast=bool(fail_fast),
        dry_run=bool(dry_run),
        created_at_utc=now,
        updated_at_utc=now,
        steps=steps,
    )


def batch_from_dict(payload: dict[str, Any]) -> BatchState:
    if not isinstance(payload, dict):
        raise SchedulerError("invalid batch payload")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise SchedulerError("invalid batch steps")

    steps: list[BatchStepState] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            continue
        steps.append(
            BatchStepState(
                step_id=str(raw.get("step_id", "")),
                config_path=str(raw.get("config_path", "")),
                mode=str(raw.get("mode", "run")) if str(raw.get("mode", "run")) in {"run", "play"} else "run",
                model_profile=_as_optional_str(raw.get("model_profile")),
                overrides=_normalize_str_list(raw.get("overrides"), field_name="step.overrides"),
                depends_on=_normalize_str_list(raw.get("depends_on"), field_name="step.depends_on"),
                status=_as_step_status(raw.get("status", "pending")),
                message=_as_optional_str(raw.get("message")),
                job_id=_as_optional_str(raw.get("job_id")),
                run_id=_as_optional_str(raw.get("run_id")),
                run_dir=_as_optional_str(raw.get("run_dir")),
                started_at_utc=_as_optional_str(raw.get("started_at_utc")),
                finished_at_utc=_as_optional_str(raw.get("finished_at_utc")),
                preview=raw.get("preview") if isinstance(raw.get("preview"), dict) else None,
            )
        )

    return BatchState(
        batch_id=str(payload.get("batch_id", "")),
        status=_as_batch_status(payload.get("status", "queued")),
        fail_fast=bool(payload.get("fail_fast", False)),
        dry_run=bool(payload.get("dry_run", False)),
        created_at_utc=str(payload.get("created_at_utc", "")),
        updated_at_utc=str(payload.get("updated_at_utc", "")),
        steps=steps,
    )


def is_batch_terminal(batch: BatchState) -> bool:
    return batch.status in {"completed", "failed", "canceled", "dry_run"}


def advance_batch_state(
    batch: BatchState,
    *,
    fetch_job: Callable[[str], dict[str, Any] | None],
    start_step: Callable[[BatchStepState], dict[str, Any]],
) -> BatchState:
    now = timestamp_utc()
    if batch.dry_run:
        batch.status = "dry_run"
        batch.updated_at_utc = now
        return batch

    if batch.status == "canceled":
        batch.updated_at_utc = now
        return batch

    step_map = {step.step_id: step for step in batch.steps}

    # Reconcile running steps first.
    for step in batch.steps:
        if step.status != "running" or not step.job_id:
            continue
        job = fetch_job(step.job_id)
        if not isinstance(job, dict):
            continue
        job_status = str(job.get("status", "running"))
        if job_status == "running" or job_status == "queued":
            continue

        step.finished_at_utc = now
        if job_status == "completed":
            step.status = "completed"
            step.message = "completed"
            step.run_id = _as_optional_str(job.get("run_id")) or step.run_id
            step.run_dir = _as_optional_str(job.get("run_dir")) or step.run_dir
            result_payload = job.get("result_payload")
            if isinstance(result_payload, dict):
                step.run_id = _as_optional_str(result_payload.get("run_id")) or step.run_id
                step.run_dir = _as_optional_str(result_payload.get("run_dir")) or step.run_dir
        elif job_status == "canceled":
            step.status = "canceled"
            step.message = "canceled"
        else:
            step.status = "failed"
            step.message = "failed"

    # Skip steps that reference dependencies that do not exist.
    for step in batch.steps:
        if step.status != "pending":
            continue
        missing = [dep for dep in step.depends_on if dep not in step_map]
        if missing:
            step.status = "skipped"
            step.message = f"missing_dependency:{','.join(missing)}"
            step.finished_at_utc = now

    # Fail-fast after first hard failure/cancel.
    has_hard_failure = any(step.status in {"failed", "canceled"} for step in batch.steps)
    if batch.fail_fast and has_hard_failure:
        for step in batch.steps:
            if step.status == "pending":
                step.status = "skipped"
                step.message = "fail_fast_after_failure"
                step.finished_at_utc = now

    # Skip steps blocked by terminal dependency failures.
    for step in batch.steps:
        if step.status != "pending":
            continue
        dep_statuses = [step_map[dep].status for dep in step.depends_on if dep in step_map]
        if any(status in {"failed", "canceled", "skipped"} for status in dep_statuses):
            step.status = "skipped"
            step.message = "dependency_not_completed"
            step.finished_at_utc = now

    # If a step is currently running we keep sequential execution and stop here.
    if any(step.status == "running" for step in batch.steps):
        batch.status = "running"
        batch.updated_at_utc = now
        return batch

    # Start the next eligible step.
    for step in batch.steps:
        if step.status != "pending":
            continue
        if not all(step_map[dep].status == "completed" for dep in step.depends_on if dep in step_map):
            continue
        handle = start_step(step)
        step.job_id = _as_optional_str(handle.get("job_id"))
        step.run_id = _as_optional_str(handle.get("run_id"))
        step.run_dir = _as_optional_str(handle.get("run_dir"))
        step.status = "running"
        step.message = "started"
        step.started_at_utc = now
        batch.status = "running"
        batch.updated_at_utc = now
        return batch

    # No running step and none started: resolve lingering pending states.
    unresolved_pending = [step for step in batch.steps if step.status == "pending"]
    if unresolved_pending:
        for step in unresolved_pending:
            step.status = "skipped"
            step.message = "unresolved_dependencies"
            step.finished_at_utc = now

    if any(step.status in {"failed", "canceled"} for step in batch.steps):
        batch.status = "failed"
    else:
        batch.status = "completed"

    batch.updated_at_utc = now
    return batch


def cancel_batch(batch: BatchState) -> BatchState:
    now = timestamp_utc()
    if batch.status in {"completed", "failed", "dry_run", "canceled"}:
        batch.updated_at_utc = now
        return batch
    for step in batch.steps:
        if step.status in {"pending", "running"}:
            step.status = "canceled"
            step.finished_at_utc = now
            step.message = "batch_canceled"
    batch.status = "canceled"
    batch.updated_at_utc = now
    return batch


def _validate_no_cycles(steps: Sequence[BatchStepDefinition]) -> None:
    known_ids = {item.step_id for item in steps}
    graph = {
        step.step_id: [dep for dep in step.depends_on if dep in known_ids]
        for step in steps
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visiting:
            raise SchedulerError(f"cyclic dependency detected around step: {node}")
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, []):
            dfs(child)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        dfs(node)


def _normalize_str_list(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SchedulerError(f"{field_name} must be a list of strings")
    values: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise SchedulerError(f"{field_name} must contain only strings")
        parsed = item.strip()
        if parsed and parsed not in values:
            values.append(parsed)
    return values


def _as_optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        parsed = value.strip()
        return parsed or None
    return None


def _as_step_id(value: Any, *, default: str) -> str:
    parsed = _as_optional_str(value)
    return parsed or default


def _as_step_status(value: Any) -> BatchStepStatus:
    parsed = str(value).strip().lower()
    if parsed in {
        "pending",
        "running",
        "completed",
        "failed",
        "canceled",
        "skipped",
        "dry_run",
    }:
        return parsed  # type: ignore[return-value]
    return "pending"


def _as_batch_status(value: Any) -> BatchStatus:
    parsed = str(value).strip().lower()
    if parsed in {"queued", "running", "completed", "failed", "canceled", "dry_run"}:
        return parsed  # type: ignore[return-value]
    return "queued"
