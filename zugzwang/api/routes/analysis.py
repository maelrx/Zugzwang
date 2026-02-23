from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from zugzwang.analysis import compare_runs, generate_markdown_report
from zugzwang.api import deps
from zugzwang.api.schemas import AnalysisCompareRequest, AnalysisCompareResponse
from zugzwang.api.services import ArtifactService


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/compare", response_model=AnalysisCompareResponse)
def create_run_comparison(
    request: AnalysisCompareRequest,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> AnalysisCompareResponse:
    try:
        comparison = compare_runs(
            run_a=request.run_a,
            run_b=request.run_b,
            runs_root=artifact_service.root,
            comparison_id=request.comparison_id,
            iterations=request.bootstrap_iterations,
            permutations=request.permutation_iterations,
            confidence=request.confidence,
            alpha=request.alpha,
            seed=request.seed,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = comparison.to_dict()
    markdown = generate_markdown_report(comparison)
    artifacts = artifact_service.save_comparison_artifacts(
        comparison_id=comparison.comparison_id,
        payload=payload,
        markdown_report=markdown,
    )
    payload["artifacts"] = artifacts
    return AnalysisCompareResponse.model_validate(payload)


@router.get("/compare/{comparison_id}", response_model=AnalysisCompareResponse)
def get_run_comparison_payload(
    comparison_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> AnalysisCompareResponse:
    try:
        payload = artifact_service.load_comparison_payload(comparison_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AnalysisCompareResponse.model_validate(payload)


@router.get("/compare/{comparison_id}/report.md", response_class=PlainTextResponse)
def get_run_comparison_markdown(
    comparison_id: str,
    artifact_service: ArtifactService = Depends(deps.get_artifact_service),
) -> PlainTextResponse:
    try:
        markdown = artifact_service.load_comparison_markdown(comparison_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(markdown, media_type="text/markdown")
