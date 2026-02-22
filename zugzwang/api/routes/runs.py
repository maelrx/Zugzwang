from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from zugzwang.api import deps
from zugzwang.api.schemas import BoardFrameResponse, GameDetailResponse, GameListItem, RunListItem, RunSummaryResponse
from zugzwang.api.services import ArtifactService, ReplayService


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunListItem])
def list_runs(
    q: str | None = Query(default=None),
    evaluated_only: bool = Query(default=False),
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> list[RunListItem]:
    filters: dict[str, Any] = {"evaluated_only": evaluated_only}
    if q:
        filters["query"] = q
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

