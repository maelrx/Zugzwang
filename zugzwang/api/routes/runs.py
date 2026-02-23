from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from zugzwang.api import deps
from zugzwang.api.schemas import BoardFrameResponse, GameDetailResponse, GameListItem, RunListItem, RunSummaryResponse
from zugzwang.api.services import ArtifactService, ReplayService


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunListItem])
def list_runs(
    q: str | None = Query(default=None),
    evaluated_only: bool = Query(default=False),
    evaluated: bool | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    status: Literal["all", "evaluated", "needs_eval", "pending_report"] | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort_by: Literal["created_at_utc", "run_id", "total_cost_usd", "elo_estimate", "acpl_overall"] = Query(
        default="created_at_utc"
    ),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> list[RunListItem]:
    effective_evaluated_only = evaluated if evaluated is not None else evaluated_only
    filters: dict[str, Any] = {
        "evaluated_only": effective_evaluated_only,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "offset": offset,
    }
    if limit is not None:
        filters["limit"] = limit
    if q:
        filters["query"] = q
    if provider:
        filters["provider"] = provider
    if model:
        filters["model"] = model
    if status:
        filters["status"] = status
    if date_from is not None:
        filters["date_from"] = date_from
    if date_to is not None:
        filters["date_to"] = date_to
    items = artifact_service.list_runs(filters=filters)
    return [RunListItem.model_validate(asdict(item)) for item in items]


@router.get("/{run_id}", response_model=RunSummaryResponse)
def get_run_summary(
    run_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> RunSummaryResponse:
    try:
        summary = artifact_service.load_run_summary(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RunSummaryResponse(
        run_meta=RunListItem.model_validate(asdict(summary.run_meta)),
        resolved_config=summary.resolved_config,
        report=summary.report,
        evaluated_report=summary.evaluated_report,
        game_count=summary.game_count,
        inferred_player_color=summary.run_meta.inferred_player_color,
        inferred_opponent_elo=summary.run_meta.inferred_opponent_elo,
        inferred_model_label=summary.run_meta.inferred_model_label,
        inferred_config_template=summary.run_meta.inferred_config_template,
    )


@router.get("/{run_id}/report", response_model=dict[str, Any])
def get_run_report(
    run_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> dict[str, Any]:
    summary = _load_summary_or_404(artifact_service, run_id)
    if summary.report is None:
        raise HTTPException(status_code=404, detail=f"Report not found for run: {run_id}")
    return summary.report


@router.get("/{run_id}/report/evaluated", response_model=dict[str, Any])
def get_run_report_evaluated(
    run_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> dict[str, Any]:
    summary = _load_summary_or_404(artifact_service, run_id)
    if summary.evaluated_report is None:
        raise HTTPException(status_code=404, detail=f"Evaluated report not found for run: {run_id}")
    return summary.evaluated_report


@router.get("/{run_id}/games", response_model=list[GameListItem])
def list_run_games(
    run_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> list[GameListItem]:
    try:
        games = artifact_service.list_games(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [GameListItem.model_validate(asdict(game)) for game in games]


@router.get("/{run_id}/games/{game_number}", response_model=GameDetailResponse)
def get_game(
    run_id: str,
    game_number: int,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> GameDetailResponse:
    try:
        game = artifact_service.load_game(run_id, game_number)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GameDetailResponse.model_validate(asdict(game))


@router.get("/{run_id}/games/{game_number}/frames", response_model=list[BoardFrameResponse])
def get_game_frames(
    run_id: str,
    game_number: int,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
    replay_service: ReplayService = Depends(deps.get_replay_service),
) -> list[BoardFrameResponse]:
    try:
        game = artifact_service.load_game(run_id, game_number)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    frames = replay_service.build_board_states(game)
    return [BoardFrameResponse.model_validate(asdict(frame)) for frame in frames]


@router.get("/{run_id}/config", response_model=dict[str, Any])
def get_run_config(
    run_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> dict[str, Any]:
    summary = _load_summary_or_404(artifact_service, run_id)
    if summary.resolved_config is None:
        raise HTTPException(status_code=404, detail=f"Resolved config not found for run: {run_id}")
    return summary.resolved_config


def _load_summary_or_404(artifact_service: ArtifactService, run_id: str):
    try:
        return artifact_service.load_run_summary(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

