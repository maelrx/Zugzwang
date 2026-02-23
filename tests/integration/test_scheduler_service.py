from __future__ import annotations

from pathlib import Path

from zugzwang.api.services.scheduler_service import SchedulerService
from zugzwang.api.types import ConfigTemplate, JobHandle, ResolvedConfigPreview
from zugzwang.infra.ids import timestamp_utc


class FakeConfigService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], str | None]] = []

    def list_templates(self) -> list[ConfigTemplate]:
        return []

    def resolve_config_preview(
        self,
        config_path: str | Path,
        overrides: list[str] | None = None,
        model_profile: str | None = None,
    ) -> ResolvedConfigPreview:
        parsed_path = str(config_path)
        parsed_overrides = list(overrides or [])
        self.calls.append((parsed_path, parsed_overrides, model_profile))
        suffix = str(len(self.calls)).zfill(2)
        return ResolvedConfigPreview(
            config_path=parsed_path,
            config_hash=f"cfg-{suffix}",
            run_id=f"preview-run-{suffix}",
            scheduled_games=5,
            estimated_total_cost_usd=1.25,
            resolved_config={"experiment": {"name": f"exp-{suffix}"}},
        )


class FakeRunService:
    def __init__(self) -> None:
        self.counter = 0
        self.jobs: dict[str, dict] = {}
        self.started_steps: list[str] = []

    def start_run(self, config_path: str, model_profile=None, overrides=None, mode="run") -> JobHandle:  # type: ignore[no-untyped-def]
        self.counter += 1
        job_id = f"job-{self.counter}"
        run_id = f"run-{self.counter}"
        run_dir = f"results/runs/{run_id}"
        handle = JobHandle(
            job_id=job_id,
            job_type="play" if mode == "play" else "run",
            status="running",
            pid=10_000 + self.counter,
            command=["python", "-m", "zugzwang.cli", mode],
            created_at_utc=timestamp_utc(),
            stdout_path=f"stdout-{job_id}.log",
            stderr_path=f"stderr-{job_id}.log",
            run_id=run_id,
            run_dir=run_dir,
            meta={"config_path": config_path, "model_profile": model_profile, "overrides": list(overrides or []), "mode": mode},
        )
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "run_id": run_id,
            "run_dir": run_dir,
            "result_payload": None,
        }
        self.started_steps.append(config_path)
        return handle

    def get_job(self, job_id: str, refresh: bool = True):  # type: ignore[no-untyped-def]
        _ = refresh
        return self.jobs.get(job_id)

    def cancel_run(self, job_id: str):  # type: ignore[no-untyped-def]
        job = self.jobs.get(job_id)
        if job:
            job["status"] = "canceled"

    def set_status(self, job_id: str, status: str) -> None:
        job = self.jobs[job_id]
        job["status"] = status
        if status == "completed":
            job["result_payload"] = {"run_id": job["run_id"], "run_dir": job["run_dir"]}



def _step_status(batch: dict, step_id: str) -> str:
    for step in batch["steps"]:
        if step["step_id"] == step_id:
            return step["status"]
    raise KeyError(step_id)


def _step_job_id(batch: dict, step_id: str) -> str:
    for step in batch["steps"]:
        if step["step_id"] == step_id:
            value = step.get("job_id")
            if isinstance(value, str):
                return value
            raise KeyError(f"step has no job id: {step_id}")
    raise KeyError(step_id)


def test_scheduler_service_executes_sequential_steps_with_dependencies(tmp_path: Path) -> None:
    run_service = FakeRunService()
    config_service = FakeConfigService()
    service = SchedulerService(
        store_root=tmp_path / "scheduler",
        run_service=run_service,
        config_service=config_service,
    )

    batch = service.create_batch(
        steps=[
            {"step_id": "a", "config_path": "configs/baselines/best_known_start.yaml"},
            {"step_id": "b", "config_path": "configs/baselines/llm_vs_random_legal.yaml", "depends_on": ["a"]},
            {"step_id": "c", "config_path": "configs/baselines/llm_vs_stockfish_800.yaml", "depends_on": ["b"]},
        ],
        fail_fast=True,
        dry_run=False,
    )

    assert batch["status"] == "running"
    assert _step_status(batch, "a") == "running"
    assert _step_status(batch, "b") == "pending"
    assert _step_status(batch, "c") == "pending"

    job_a = _step_job_id(batch, "a")
    run_service.set_status(job_a, "completed")
    batch = service.get_batch(batch["batch_id"], refresh=True)
    assert _step_status(batch, "a") == "completed"
    assert _step_status(batch, "b") == "running"
    assert _step_status(batch, "c") == "pending"

    job_b = _step_job_id(batch, "b")
    run_service.set_status(job_b, "completed")
    batch = service.get_batch(batch["batch_id"], refresh=True)
    assert _step_status(batch, "b") == "completed"
    assert _step_status(batch, "c") == "running"

    job_c = _step_job_id(batch, "c")
    run_service.set_status(job_c, "completed")
    batch = service.get_batch(batch["batch_id"], refresh=True)

    assert batch["status"] == "completed"
    assert _step_status(batch, "c") == "completed"
    assert len(run_service.started_steps) == 3


def test_scheduler_service_marks_missing_dependency_as_skipped(tmp_path: Path) -> None:
    run_service = FakeRunService()
    service = SchedulerService(
        store_root=tmp_path / "scheduler",
        run_service=run_service,
        config_service=FakeConfigService(),
    )

    batch = service.create_batch(
        steps=[
            {"step_id": "a", "config_path": "configs/baselines/best_known_start.yaml"},
            {"step_id": "b", "config_path": "configs/baselines/llm_vs_random_legal.yaml", "depends_on": ["missing"]},
        ],
        fail_fast=False,
        dry_run=False,
    )

    assert _step_status(batch, "b") == "skipped"

    job_a = _step_job_id(batch, "a")
    run_service.set_status(job_a, "completed")
    batch = service.get_batch(batch["batch_id"], refresh=True)

    assert batch["status"] == "completed"
    assert _step_status(batch, "b") == "skipped"


def test_scheduler_service_fail_fast_skips_remaining_after_failure(tmp_path: Path) -> None:
    run_service = FakeRunService()
    service = SchedulerService(
        store_root=tmp_path / "scheduler",
        run_service=run_service,
        config_service=FakeConfigService(),
    )

    batch = service.create_batch(
        steps=[
            {"step_id": "a", "config_path": "configs/baselines/best_known_start.yaml"},
            {"step_id": "b", "config_path": "configs/baselines/llm_vs_random_legal.yaml"},
        ],
        fail_fast=True,
        dry_run=False,
    )

    job_a = _step_job_id(batch, "a")
    run_service.set_status(job_a, "failed")
    batch = service.get_batch(batch["batch_id"], refresh=True)

    assert batch["status"] == "failed"
    assert _step_status(batch, "a") == "failed"
    assert _step_status(batch, "b") == "skipped"


def test_scheduler_service_dry_run_does_not_start_jobs(tmp_path: Path) -> None:
    run_service = FakeRunService()
    config_service = FakeConfigService()
    service = SchedulerService(
        store_root=tmp_path / "scheduler",
        run_service=run_service,
        config_service=config_service,
    )

    batch = service.create_batch(
        steps=[
            {"step_id": "a", "config_path": "configs/baselines/best_known_start.yaml"},
            {"step_id": "b", "config_path": "configs/baselines/llm_vs_random_legal.yaml", "mode": "play"},
        ],
        fail_fast=True,
        dry_run=True,
    )

    assert batch["status"] == "dry_run"
    assert _step_status(batch, "a") == "dry_run"
    assert _step_status(batch, "b") == "dry_run"
    assert len(run_service.started_steps) == 0
    assert len(config_service.calls) == 2
