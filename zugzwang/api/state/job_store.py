from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zugzwang.infra.ids import timestamp_utc
from zugzwang.api.types import JobHandle, JobStatus


DEFAULT_JOBS_PATH = Path("results/ui_jobs/jobs.jsonl")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()


def append_event(
    event_type: str,
    payload: dict[str, Any],
    jobs_path: str | Path = DEFAULT_JOBS_PATH,
) -> None:
    path = Path(jobs_path)
    _ensure_parent(path)
    event = {
        "ts_utc": timestamp_utc(),
        "event_type": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(event) + "\n")


def create_job(job: JobHandle, jobs_path: str | Path = DEFAULT_JOBS_PATH) -> None:
    append_event("job_created", job.to_dict(), jobs_path=jobs_path)


def update_job(
    job_id: str,
    status: JobStatus,
    patch: dict[str, Any] | None = None,
    jobs_path: str | Path = DEFAULT_JOBS_PATH,
) -> None:
    payload = {"job_id": job_id, "status": status, "patch": patch or {}}
    append_event("job_updated", payload, jobs_path=jobs_path)


def list_jobs(jobs_path: str | Path = DEFAULT_JOBS_PATH) -> list[dict[str, Any]]:
    path = Path(jobs_path)
    if not path.exists():
        return []

    jobs: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("event_type")
            payload = event.get("payload", {})
            if event_type == "job_created":
                job_id = payload.get("job_id")
                if not job_id:
                    continue
                jobs[job_id] = payload
                jobs[job_id]["updated_at_utc"] = event.get("ts_utc")
            elif event_type == "job_updated":
                job_id = payload.get("job_id")
                if not job_id or job_id not in jobs:
                    continue
                jobs[job_id]["status"] = payload.get("status", jobs[job_id].get("status"))
                patch = payload.get("patch", {})
                if isinstance(patch, dict):
                    jobs[job_id].update(patch)
                jobs[job_id]["updated_at_utc"] = event.get("ts_utc")
    return sorted(jobs.values(), key=lambda x: x.get("created_at_utc", ""), reverse=True)


def get_job(job_id: str, jobs_path: str | Path = DEFAULT_JOBS_PATH) -> dict[str, Any] | None:
    jobs = list_jobs(jobs_path=jobs_path)
    for job in jobs:
        if job.get("job_id") == job_id:
            return job
    return None

