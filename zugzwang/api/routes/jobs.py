from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from zugzwang.api import deps
from zugzwang.api.schemas import JobResponse, RunProgressResponse
from zugzwang.api.services import RunService
from zugzwang.ui.types import RunProgress


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(run_service: RunService = Depends(deps.get_run_service)) -> list[JobResponse]:
    jobs = run_service.list_jobs(refresh=True)
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, run_service: RunService = Depends(deps.get_run_service)) -> JobResponse:
    job = run_service.get_job(job_id, refresh=True)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobResponse.model_validate(job)


@router.get("/{job_id}/progress", response_model=RunProgressResponse)
def get_job_progress(job_id: str, run_service: RunService = Depends(deps.get_run_service)) -> RunProgressResponse:
    try:
        progress = run_service.get_run_progress(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _progress_response(progress)


def _progress_response(progress: RunProgress) -> RunProgressResponse:
    return RunProgressResponse.model_validate(asdict(progress))

