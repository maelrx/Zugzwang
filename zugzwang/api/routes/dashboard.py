from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from zugzwang.api import deps
from zugzwang.api.schemas import DashboardKpisResponse, DashboardTimelinePointResponse
from zugzwang.api.services import ArtifactService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpisResponse)
def get_dashboard_kpis(
    timeline_limit: int = Query(default=40, ge=1, le=200),
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> DashboardKpisResponse:
    kpis = artifact_service.build_dashboard_kpis(timeline_limit=timeline_limit)
    return DashboardKpisResponse(
        total_runs=kpis.total_runs,
        runs_with_reports=kpis.runs_with_reports,
        evaluated_runs=kpis.evaluated_runs,
        best_elo=kpis.best_elo,
        avg_acpl=kpis.avg_acpl,
        total_cost_usd=kpis.total_cost_usd,
        last_run_id=kpis.last_run_id,
        timeline=[DashboardTimelinePointResponse.model_validate(asdict(item)) for item in kpis.timeline],
    )
