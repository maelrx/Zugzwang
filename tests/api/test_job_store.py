from __future__ import annotations

import json
from pathlib import Path

from zugzwang.infra.ids import timestamp_utc
from zugzwang.api.services.job_runtime import refresh_job
from zugzwang.api.state.job_store import create_job, get_job, update_job
from zugzwang.api.types import JobHandle


def test_job_store_create_and_update(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.jsonl"
    handle = JobHandle(
        job_id="job-1",
        job_type="run",
        status="running",
        pid=123,
        command=["python", "-m", "zugzwang.cli", "run"],
        created_at_utc=timestamp_utc(),
        stdout_path=str(tmp_path / "stdout.log"),
        stderr_path=str(tmp_path / "stderr.log"),
        run_id=None,
        run_dir=None,
        meta={},
    )
    create_job(handle, jobs_path=jobs_path)
    update_job("job-1", "failed", patch={"exit_code": 1}, jobs_path=jobs_path)

    loaded = get_job("job-1", jobs_path=jobs_path)
    assert loaded is not None
    assert loaded["status"] == "failed"
    assert loaded["exit_code"] == 1


def test_refresh_job_reads_exit_payload_and_marks_completed(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.jsonl"
    exit_payload_path = tmp_path / "job-status.json"
    exit_payload = {
        "exit_code": 0,
        "payload": {
            "run_id": "sample-run-id",
            "run_dir": "results/runs/sample-run-id",
        },
    }
    exit_payload_path.write_text(json.dumps(exit_payload), encoding="utf-8")

    handle = JobHandle(
        job_id="job-2",
        job_type="run",
        status="running",
        pid=999999,
        command=["python", "-m", "zugzwang.cli", "run"],
        created_at_utc=timestamp_utc(),
        stdout_path=str(tmp_path / "stdout.log"),
        stderr_path=str(tmp_path / "stderr.log"),
        run_id=None,
        run_dir=None,
        meta={"exit_code_path": str(exit_payload_path)},
    )
    create_job(handle, jobs_path=jobs_path)

    refreshed = refresh_job("job-2", jobs_path=jobs_path)
    assert refreshed is not None
    assert refreshed["status"] == "completed"
    assert refreshed["run_id"] == "sample-run-id"
    assert refreshed["run_dir"] == "results/runs/sample-run-id"


def test_refresh_job_preserves_canceled_when_exit_code_nonzero_after_cancel(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.jsonl"
    exit_payload_path = tmp_path / "job-status-canceled.json"
    exit_payload = {
        "exit_code": 1,
        "payload": {
            "run_id": "sample-run-id",
            "run_dir": "results/runs/sample-run-id",
        },
    }
    exit_payload_path.write_text(json.dumps(exit_payload), encoding="utf-8")

    handle = JobHandle(
        job_id="job-3",
        job_type="run",
        status="running",
        pid=999999,
        command=["python", "-m", "zugzwang.cli", "run"],
        created_at_utc=timestamp_utc(),
        stdout_path=str(tmp_path / "stdout.log"),
        stderr_path=str(tmp_path / "stderr.log"),
        run_id=None,
        run_dir=None,
        meta={
            "exit_code_path": str(exit_payload_path),
            "cancel_requested_utc": timestamp_utc(),
        },
    )
    create_job(handle, jobs_path=jobs_path)

    refreshed = refresh_job("job-3", jobs_path=jobs_path)
    assert refreshed is not None
    assert refreshed["status"] == "canceled"

