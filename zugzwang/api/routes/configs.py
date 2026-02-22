from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from zugzwang.api import deps
from zugzwang.api.schemas import (
    ConfigListResponse,
    ModelProviderPresetResponse,
    ConfigPreviewResponse,
    ConfigTemplate,
    ConfigValidateRequest,
    ConfigValidateResponse,
)
from zugzwang.api.services import ConfigService, ModelCatalogService


router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("", response_model=ConfigListResponse)
def list_configs(config_service: ConfigService = Depends(deps.get_config_service)) -> ConfigListResponse:
    templates = config_service.list_templates()
    baselines: list[ConfigTemplate] = []
    ablations: list[ConfigTemplate] = []
    for template in templates:
        payload = ConfigTemplate.model_validate(asdict(template))
        if template.category == "baselines":
            baselines.append(payload)
        elif template.category == "ablations":
            ablations.append(payload)
    return ConfigListResponse(baselines=baselines, ablations=ablations)


@router.get("/model-catalog", response_model=list[ModelProviderPresetResponse])
def list_model_catalog(
    catalog_service: ModelCatalogService = Depends(deps.get_model_catalog_service),
) -> list[ModelProviderPresetResponse]:
    presets = catalog_service.list_provider_presets()
    return [ModelProviderPresetResponse.model_validate(asdict(item)) for item in presets]


@router.post("/validate", response_model=ConfigValidateResponse)
def validate_config(
    payload: ConfigValidateRequest,
    config_service: ConfigService = Depends(deps.get_config_service),
) -> ConfigValidateResponse:
    result = config_service.validate_config(
        config_path=payload.config_path,
        overrides=payload.overrides,
        model_profile=payload.model_profile,
    )
    return ConfigValidateResponse.model_validate(asdict(result))


@router.post("/preview", response_model=ConfigPreviewResponse)
def preview_config(
    payload: ConfigValidateRequest,
    config_service: ConfigService = Depends(deps.get_config_service),
) -> ConfigPreviewResponse:
    try:
        preview = config_service.resolve_config_preview(
            config_path=payload.config_path,
            overrides=payload.overrides,
            model_profile=payload.model_profile,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConfigPreviewResponse.model_validate(asdict(preview))
