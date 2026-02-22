from __future__ import annotations

from functools import lru_cache

from zugzwang.api.services import ArtifactService, ConfigService, EvaluationService, ReplayService, RunService


@lru_cache(maxsize=1)
def get_config_service() -> ConfigService:
    return ConfigService()


@lru_cache(maxsize=1)
def get_run_service() -> RunService:
    return RunService()


@lru_cache(maxsize=1)
def get_artifact_service() -> ArtifactService:
    return ArtifactService()


@lru_cache(maxsize=1)
def get_replay_service() -> ReplayService:
    return ReplayService()


@lru_cache(maxsize=1)
def get_evaluation_service() -> EvaluationService:
    return EvaluationService()

