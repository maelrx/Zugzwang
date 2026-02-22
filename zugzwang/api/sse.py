from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Request


TERMINAL_JOB_STATES: set[str] = {"completed", "failed", "canceled"}


def build_sse_event(event: str, data: Any) -> dict[str, Any]:
    return {"event": event, "data": data}


async def iter_job_log_events(
    *,
    job_id: str,
    request: Request,
    run_service: Any,
    poll_interval_seconds: float = 0.2,
) -> AsyncIterator[dict[str, Any]]:
    stdout_offset = 0
    stderr_offset = 0
    stdout_carry = ""
    stderr_carry = ""

    while True:
        if await request.is_disconnected():
            break

        job = run_service.get_job(job_id, refresh=True)
        if job is None:
            yield build_sse_event("error", f"Job not found: {job_id}")
            break

        stdout_path = _as_path(job.get("stdout_path"))
        stderr_path = _as_path(job.get("stderr_path"))

        stdout_offset, stdout_lines, stdout_carry = _read_new_lines(stdout_path, stdout_offset, stdout_carry)
        stderr_offset, stderr_lines, stderr_carry = _read_new_lines(stderr_path, stderr_offset, stderr_carry)

        for line in stdout_lines:
            yield build_sse_event("stdout", line)
        for line in stderr_lines:
            yield build_sse_event("stderr", line)

        status = str(job.get("status", "queued"))
        if status in TERMINAL_JOB_STATES:
            if stdout_carry:
                yield build_sse_event("stdout", stdout_carry)
            if stderr_carry:
                yield build_sse_event("stderr", stderr_carry)
            yield build_sse_event("done", {"status": status})
            break

        await asyncio.sleep(poll_interval_seconds)


def _read_new_lines(path: Path | None, offset: int, carry: str) -> tuple[int, list[str], str]:
    if path is None or not path.exists():
        return offset, [], carry

    if offset < 0:
        offset = 0

    file_size = path.stat().st_size
    if offset > file_size:
        offset = 0
        carry = ""

    with path.open("rb") as fp:
        fp.seek(offset)
        chunk = fp.read()

    if not chunk:
        return offset, [], carry

    text = chunk.decode("utf-8", errors="replace")
    combined = carry + text
    lines = combined.splitlines()

    ends_with_newline = combined.endswith("\n") or combined.endswith("\r")
    if ends_with_newline:
        new_carry = ""
    else:
        new_carry = lines.pop() if lines else combined

    return offset + len(chunk), lines, new_carry


def _as_path(value: Any) -> Path | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return Path(stripped)
