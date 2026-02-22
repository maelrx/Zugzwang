from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


JobStatus = Literal["queued", "running", "completed", "failed", "canceled"]
JobType = Literal["run", "play", "evaluate"]


@dataclass
class ConfigTemplate:
    name: str
    path: str
    category: str


@dataclass
class ValidationResult:
    ok: bool
    message: str
    config_hash: str | None = None
    resolved_config: dict[str, Any] | None = None


@dataclass
class ResolvedConfigPreview:
    config_path: str
    config_hash: str
    run_id: str
    scheduled_games: int
    estimated_total_cost_usd: float | None
    resolved_config: dict[str, Any]


@dataclass
class JobHandle:
    job_id: str
    job_type: JobType
    status: JobStatus
    pid: int | None
    command: list[str]
    created_at_utc: str
    stdout_path: str
    stderr_path: str
    run_id: str | None = None
    run_dir: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CancelResult:
    ok: bool
    message: str
    status: JobStatus


@dataclass
class RunMeta:
    run_id: str
    run_dir: str
    created_at_utc: str | None
    config_hash: str | None
    report_exists: bool
    evaluated_report_exists: bool


@dataclass
class RunSummary:
    run_meta: RunMeta
    resolved_config: dict[str, Any] | None
    report: dict[str, Any] | None
    evaluated_report: dict[str, Any] | None
    game_count: int


@dataclass
class GameMeta:
    game_number: int
    path: str


@dataclass
class BoardStateFrame:
    ply_number: int
    fen: str
    svg: str
    move_uci: str | None
    move_san: str | None
    color: str | None
    raw_response: str | None


@dataclass
class PlyMetrics:
    tokens_input: int
    tokens_output: int
    latency_ms: int
    retry_count: int
    parse_ok: bool
    is_legal: bool
    cost_usd: float
    provider_model: str
    feedback_level: str
    error: str | None


@dataclass
class GameRecordView:
    game_number: int
    result: str
    termination: str
    duration_seconds: float
    total_cost_usd: float
    total_tokens: dict[str, int]
    moves: list[dict[str, Any]]


@dataclass
class RunProgress:
    run_id: str | None
    status: JobStatus
    games_written: int
    games_target: int | None
    run_dir: str | None
    stopped_due_to_budget: bool | None
    budget_stop_reason: str | None
    latest_report: dict[str, Any] | None
    log_tail: str


@dataclass
class EvalResult:
    status: JobStatus
    output_report: str | None
    payload: dict[str, Any] | None
    log_tail: str
