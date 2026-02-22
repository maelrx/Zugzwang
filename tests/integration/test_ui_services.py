from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from zugzwang.api.services.evaluation_service import EvaluationService
from zugzwang.api.services.run_service import RunService


ROOT = Path(__file__).resolve().parents[2]


def _wait_for_terminal_status(service: RunService | EvaluationService, job_id: str, timeout_seconds: float = 60.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if isinstance(service, RunService):
            job = service.get_job(job_id, refresh=True)
        else:
            jobs = service.list_jobs(refresh=True)
            job = next((item for item in jobs if item.get("job_id") == job_id), None)
        if job and job.get("status") in {"completed", "failed", "canceled"}:
            return job
        time.sleep(0.2)
    raise TimeoutError(f"job did not complete within {timeout_seconds}s: {job_id}")


def test_run_service_play_job_completes(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.jsonl"
    service = RunService(jobs_path=jobs_path)
    handle = service.start_run(
        config_path=str(ROOT / "configs" / "baselines" / "best_known_start.yaml"),
        mode="play",
        overrides=[
            "runtime.max_plies=4",
            f"runtime.output_dir={tmp_path.as_posix()}",
        ],
    )

    job = _wait_for_terminal_status(service, handle.job_id, timeout_seconds=90.0)
    assert job["status"] == "completed"

    progress = service.get_run_progress(handle.job_id)
    assert progress.run_dir is not None
    assert Path(progress.run_dir).exists()


def test_evaluation_service_job_completes_when_stockfish_available(tmp_path: Path) -> None:
    stockfish_path = os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")
    if not stockfish_path:
        pytest.skip("Stockfish not available in environment")

    jobs_path = tmp_path / "jobs.jsonl"
    run_service = RunService(jobs_path=jobs_path)
    run_handle = run_service.start_run(
        config_path=str(ROOT / "configs" / "baselines" / "best_known_start.yaml"),
        mode="play",
        overrides=[
            "runtime.max_plies=4",
            f"runtime.output_dir={tmp_path.as_posix()}",
        ],
    )
    run_job = _wait_for_terminal_status(run_service, run_handle.job_id, timeout_seconds=90.0)
    assert run_job["status"] == "completed"

    progress = run_service.get_run_progress(run_handle.job_id)
    assert progress.run_dir is not None

    eval_service = EvaluationService(jobs_path=jobs_path)
    eval_handle = eval_service.start_evaluation(run_dir=progress.run_dir, player_color="black")
    eval_job = _wait_for_terminal_status(eval_service, eval_handle.job_id, timeout_seconds=180.0)

    assert eval_job["status"] == "completed"
    result = eval_service.get_evaluation_result(eval_handle.job_id)
    assert result.output_report is not None
    assert Path(result.output_report).exists()
