from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["queued", "running", "completed", "failed", "canceled"]
JobType = Literal["run", "play", "evaluate"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ConfigTemplate(ApiModel):
    name: str
    path: str
    category: str


class ConfigListResponse(ApiModel):
    baselines: list[ConfigTemplate] = Field(default_factory=list)
    ablations: list[ConfigTemplate] = Field(default_factory=list)


class ModelOptionResponse(ApiModel):
    id: str
    label: str
    recommended: bool = False


class ModelProviderPresetResponse(ApiModel):
    provider: str
    provider_label: str
    api_style: str
    base_url: str
    api_key_env: str
    notes: str
    models: list[ModelOptionResponse] = Field(default_factory=list)


class ConfigValidateRequest(ApiModel):
    config_path: str
    overrides: list[str] = Field(default_factory=list)
    model_profile: str | None = None


class ConfigValidateResponse(ApiModel):
    ok: bool
    message: str
    config_hash: str | None = None
    resolved_config: dict[str, Any] | None = None


class ConfigPreviewResponse(ApiModel):
    config_path: str
    config_hash: str
    run_id: str
    scheduled_games: int
    estimated_total_cost_usd: float | None = None
    resolved_config: dict[str, Any]


class JobResponse(ApiModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    pid: int | None = None
    command: list[str] = Field(default_factory=list)
    created_at_utc: str
    updated_at_utc: str | None = None
    stdout_path: str
    stderr_path: str
    run_id: str | None = None
    run_dir: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] | None = None
    exit_code: int | None = None


class StartJobRequest(ApiModel):
    config_path: str
    model_profile: str | None = None
    overrides: list[str] = Field(default_factory=list)


class StartEvalRequest(ApiModel):
    run_dir: str
    player_color: Literal["white", "black"] = "black"
    opponent_elo: float | None = None
    output_filename: str = "experiment_report_evaluated.json"


class CancelJobResponse(ApiModel):
    ok: bool
    message: str
    status: JobStatus


class RunProgressResponse(ApiModel):
    run_id: str | None
    status: JobStatus
    games_written: int
    games_target: int | None = None
    run_dir: str | None = None
    stopped_due_to_budget: bool | None = None
    budget_stop_reason: str | None = None
    latest_report: dict[str, Any] | None = None
    log_tail: str = ""


class RunListItem(ApiModel):
    run_id: str
    run_dir: str
    created_at_utc: str | None = None
    config_hash: str | None = None
    report_exists: bool
    evaluated_report_exists: bool


class RunSummaryResponse(ApiModel):
    run_meta: RunListItem
    resolved_config: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    evaluated_report: dict[str, Any] | None = None
    game_count: int


class GameListItem(ApiModel):
    game_number: int
    path: str


class GameDetailResponse(ApiModel):
    game_number: int
    result: str
    termination: str
    duration_seconds: float
    total_cost_usd: float
    total_tokens: dict[str, int] = Field(default_factory=dict)
    moves: list[dict[str, Any]] = Field(default_factory=list)


class BoardFrameResponse(ApiModel):
    ply_number: int
    fen: str
    svg: str
    move_uci: str | None = None
    move_san: str | None = None
    color: str | None = None
    raw_response: str | None = None


class EnvCheckResponse(ApiModel):
    provider: str
    ok: bool
    message: str
