from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from zugzwang.infra.ids import timestamp_utc
from zugzwang.api.services.paths import project_root, ui_jobs_root
from zugzwang.api.services.process_utils import is_pid_running, python_executable, tail_text, terminate_pid
from zugzwang.api.state.job_store import DEFAULT_JOBS_PATH, create_job, get_job, list_jobs, update_job
from zugzwang.api.types import CancelResult, JobHandle, JobStatus, JobType


TERMINAL_STATES: set[str] = {"completed", "failed", "canceled"}


def _make_job_id(job_type: JobType) -> str:
    suffix = uuid.uuid4().hex[:8]
    stamp = timestamp_utc().replace(":", "").replace("-", "")
    return f"{job_type}-{stamp}-{suffix}"


def _job_paths(job_id: str) -> tuple[Path, Path, Path]:
    root = ui_jobs_root()
    stdout_path = root / "logs" / f"{job_id}.stdout.log"
    stderr_path = root / "logs" / f"{job_id}.stderr.log"
    status_path = root / "status" / f"{job_id}.json"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    return stdout_path, stderr_path, status_path


def start_job(
    *,
    job_type: JobType,
    command: list[str],
    run_id: str | None = None,
    run_dir: str | None = None,
    meta: dict[str, Any] | None = None,
    jobs_path: str | Path = DEFAULT_JOBS_PATH,
    working_dir: str | Path | None = None,
) -> JobHandle:
    job_id = _make_job_id(job_type)
    stdout_path, stderr_path, status_path = _job_paths(job_id)

    merged_meta = dict(meta or {})
    merged_meta["exit_code_path"] = str(status_path)

    handle = JobHandle(
        job_id=job_id,
        job_type=job_type,
        status="queued",
        pid=None,
        command=command,
        created_at_utc=timestamp_utc(),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        run_id=run_id,
        run_dir=run_dir,
        meta=merged_meta,
    )
    create_job(handle, jobs_path=jobs_path)
    wrapper_cmd = [
        python_executable(),
        "-m",
        "zugzwang.api.services.job_worker",
        "--stdout-path",
        str(stdout_path),
        "--stderr-path",
        str(stderr_path),
        "--exit-code-path",
        str(status_path),
        "--workdir",
        str(Path(working_dir or project_root())),
        "--",
        *command,
    ]
    process = subprocess.Popen(wrapper_cmd, cwd=str(project_root()))
    update_job(
        job_id,
        "running",
        patch={"pid": int(process.pid)},
        jobs_path=jobs_path,
    )
    handle.status = "running"
    handle.pid = int(process.pid)
    return handle


def _read_exit_payload(status_path: str | Path) -> dict[str, Any] | None:
    path = Path(status_path)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def refresh_job(job_id: str, jobs_path: str | Path = DEFAULT_JOBS_PATH) -> dict[str, Any] | None:
    job = get_job(job_id, jobs_path=jobs_path)
    if not job:
        return None

    status = str(job.get("status", "queued"))
    if status in TERMINAL_STATES:
        return job

    pid = int(job.get("pid") or 0)
    if pid > 0 and is_pid_running(pid):
        return job

    meta = dict(job.get("meta") or {})
    cancel_requested = _cancel_requested(meta)
    status_path = meta.get("exit_code_path")
    exit_payload = _read_exit_payload(status_path) if status_path else None

    patch: dict[str, Any] = {}
    new_status: JobStatus = "failed"

    if exit_payload:
        exit_code = int(exit_payload.get("exit_code", 1))
        if exit_code == 0:
            new_status = "completed"
        elif cancel_requested:
            new_status = "canceled"
        else:
            new_status = "failed"
        payload = exit_payload.get("payload")

        meta["exit"] = exit_payload
        patch["meta"] = meta
        patch["exit_code"] = exit_code

        if isinstance(payload, dict):
            run_id = payload.get("run_id")
            run_dir = payload.get("run_dir")
            if isinstance(run_id, str):
                patch["run_id"] = run_id
            if isinstance(run_dir, str):
                patch["run_dir"] = run_dir
            patch["result_payload"] = payload
    else:
        if cancel_requested:
            new_status = "canceled"
        patch["meta"] = meta

    update_job(job_id, new_status, patch=patch, jobs_path=jobs_path)
    return get_job(job_id, jobs_path=jobs_path)


def refresh_all_jobs(jobs_path: str | Path = DEFAULT_JOBS_PATH) -> list[dict[str, Any]]:
    current = list_jobs(jobs_path=jobs_path)
    for job in current:
        identifier = job.get("job_id")
        if isinstance(identifier, str):
            refresh_job(identifier, jobs_path=jobs_path)
    return list_jobs(jobs_path=jobs_path)


def cancel_job(job_id: str, jobs_path: str | Path = DEFAULT_JOBS_PATH) -> CancelResult:
    job = get_job(job_id, jobs_path=jobs_path)
    if not job:
        return CancelResult(ok=False, message=f"job not found: {job_id}", status="failed")

    status = str(job.get("status", "queued"))
    if status in TERMINAL_STATES:
        terminal_status: JobStatus = "failed"
        if status in {"completed", "failed", "canceled"}:
            terminal_status = status
        return CancelResult(ok=False, message="job already finished", status=terminal_status)

    current_status: JobStatus = "queued" if status == "queued" else "running"
    meta = dict(job.get("meta") or {})
    meta["cancel_requested_utc"] = timestamp_utc()
    update_job(job_id, current_status, patch={"meta": meta}, jobs_path=jobs_path)

    pid = int(job.get("pid") or 0)
    if pid <= 0:
        update_job(job_id, "canceled", patch=None, jobs_path=jobs_path)
        return CancelResult(ok=True, message="job marked as canceled", status="canceled")

    if not is_pid_running(pid):
        update_job(job_id, "canceled", patch=None, jobs_path=jobs_path)
        return CancelResult(ok=True, message="job already stopped and marked as canceled", status="canceled")

    ok = terminate_pid(pid)
    if ok:
        update_job(job_id, "canceled", patch=None, jobs_path=jobs_path)
        return CancelResult(ok=True, message="job canceled", status="canceled")

    return CancelResult(ok=False, message="failed to cancel process", status="failed")


def job_log_tail(job: dict[str, Any], max_chars: int = 8000) -> str:
    stdout_path = job.get("stdout_path")
    stderr_path = job.get("stderr_path")
    stdout = tail_text(stdout_path, max_chars=max_chars // 2) if stdout_path else ""
    stderr = tail_text(stderr_path, max_chars=max_chars // 2) if stderr_path else ""
    if stderr:
        if stdout:
            return f"{stdout}\n\n[stderr]\n{stderr}"
        return f"[stderr]\n{stderr}"
    return stdout


def _cancel_requested(meta: dict[str, Any]) -> bool:
    value = meta.get("cancel_requested_utc")
    return isinstance(value, str) and bool(value.strip())


