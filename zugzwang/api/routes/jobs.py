from __future__ import annotations

from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from zugzwang.api import deps
from zugzwang.api.schemas import CancelJobResponse, JobResponse, RunProgressResponse, StartEvalRequest, StartJobRequest
from zugzwang.api.services import EvaluationService, RunService
from zugzwang.api.sse import iter_job_log_events
from zugzwang.api.types import RunProgress


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


@router.post("/run", response_model=JobResponse)
def start_run(
    payload: StartJobRequest,
    run_service: RunService = Depends(deps.get_run_service),
) -> JobResponse:
    try:
        handle = run_service.start_run(
            config_path=payload.config_path,
            model_profile=payload.model_profile,
            overrides=payload.overrides,
            mode="run",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(handle)


@router.post("/play", response_model=JobResponse)
def start_play(
    payload: StartJobRequest,
    run_service: RunService = Depends(deps.get_run_service),
) -> JobResponse:
    try:
        handle = run_service.start_run(
            config_path=payload.config_path,
            model_profile=payload.model_profile,
            overrides=payload.overrides,
            mode="play",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(handle)


@router.post("/evaluate", response_model=JobResponse)
def start_evaluation(
    payload: StartEvalRequest,
    evaluation_service: EvaluationService = Depends(deps.get_evaluation_service),
) -> JobResponse:
    try:
        handle = evaluation_service.start_evaluation(
            run_dir=payload.run_dir,
            player_color=payload.player_color,
            opponent_elo=payload.opponent_elo,
            output_filename=payload.output_filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(handle)


@router.delete("/{job_id}", response_model=CancelJobResponse)
def cancel_job(job_id: str, run_service: RunService = Depends(deps.get_run_service)) -> CancelJobResponse:
    result = run_service.cancel_run(job_id)
    return CancelJobResponse.model_validate(asdict(result))


@router.get("/{job_id}/logs")
async def stream_job_logs(
    job_id: str,
    request: Request,
    run_service: RunService = Depends(deps.get_run_service),
) -> EventSourceResponse:
    job = run_service.get_job(job_id, refresh=True)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return EventSourceResponse(iter_job_log_events(job_id=job_id, request=request, run_service=run_service))


def _progress_response(progress: RunProgress) -> RunProgressResponse:
    return RunProgressResponse.model_validate(asdict(progress))


def _job_response(job: object) -> JobResponse:
    if is_dataclass(job):
        return JobResponse.model_validate(asdict(job))
    if isinstance(job, dict):
        return JobResponse.model_validate(job)
    raise ValueError(f"Unsupported job payload type: {type(job)!r}")
