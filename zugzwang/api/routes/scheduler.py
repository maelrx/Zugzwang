from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from zugzwang.api import deps
from zugzwang.api.schemas import SchedulerBatchCreateRequest, SchedulerBatchResponse
from zugzwang.api.services import SchedulerService


router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/batches", response_model=SchedulerBatchResponse)
def create_batch(
    payload: SchedulerBatchCreateRequest,
    scheduler_service: SchedulerService = Depends(deps.get_scheduler_service),
) -> SchedulerBatchResponse:
    try:
        batch = scheduler_service.create_batch(
            steps=[step.model_dump() for step in payload.steps],
            fail_fast=payload.fail_fast,
            dry_run=payload.dry_run,
            batch_id=payload.batch_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SchedulerBatchResponse.model_validate(batch)


@router.get("/batches", response_model=list[SchedulerBatchResponse])
def list_batches(
    limit: int = Query(default=50, ge=1, le=200),
    refresh: bool = Query(default=True),
    scheduler_service: SchedulerService = Depends(deps.get_scheduler_service),
) -> list[SchedulerBatchResponse]:
    batches = scheduler_service.list_batches(limit=limit, refresh=refresh)
    return [SchedulerBatchResponse.model_validate(item) for item in batches]


@router.get("/batches/{batch_id}", response_model=SchedulerBatchResponse)
def get_batch(
    batch_id: str,
    refresh: bool = Query(default=True),
    scheduler_service: SchedulerService = Depends(deps.get_scheduler_service),
) -> SchedulerBatchResponse:
    try:
        batch = scheduler_service.get_batch(batch_id, refresh=refresh)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SchedulerBatchResponse.model_validate(batch)


@router.delete("/batches/{batch_id}", response_model=SchedulerBatchResponse)
def cancel_batch(
    batch_id: str,
    scheduler_service: SchedulerService = Depends(deps.get_scheduler_service),
) -> SchedulerBatchResponse:
    try:
        batch = scheduler_service.cancel_batch(batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SchedulerBatchResponse.model_validate(batch)
