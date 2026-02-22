from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from zugzwang.api import deps
from zugzwang.api.schemas import ConfigListResponse, ConfigTemplate
from zugzwang.api.services import ConfigService


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

