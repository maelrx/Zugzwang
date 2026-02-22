from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GameState:
    fen: str
    pgn: str
    move_number: int
    ply_number: int
    active_color: str
    legal_moves_uci: list[str]
    legal_moves_san: list[str]
    phase: str
    is_check: bool
    is_terminal: bool
    termination_reason: str | None
    history_uci: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MoveDecision:
    move_uci: str
    move_san: str
    raw_response: str
    parse_ok: bool
    is_legal: bool
    retry_count: int
    tokens_input: int
    tokens_output: int
    latency_ms: int
    provider_model: str
    provider_calls: int = 0
    feedback_level: str = "rich"
    error: str | None = None
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MoveRecord:
    ply_number: int
    color: str
    fen_before: str
    move_decision: MoveDecision

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["move_decision"] = self.move_decision.to_dict()
        return output


@dataclass
class GameRecord:
    experiment_id: str
    game_number: int
    config_hash: str
    seed: int
    players: dict[str, Any]
    moves: list[MoveRecord]
    result: str
    termination: str
    token_usage: dict[str, int]
    cost_usd: float
    duration_seconds: float
    timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "game_number": self.game_number,
            "config_hash": self.config_hash,
            "seed": self.seed,
            "players": self.players,
            "moves": [move.to_dict() for move in self.moves],
            "result": self.result,
            "termination": self.termination,
            "token_usage": self.token_usage,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class ExperimentReport:
    schema_version: str
    experiment_id: str
    config_hash: str
    num_games_target: int
    num_games_scheduled: int
    num_games_valid: int
    completion_rate: float
    wins: int
    draws: int
    losses: int
    win_loss_score: float
    elo_estimate: float | None
    elo_ci_95: list[float] | None
    acpl_overall: float
    acpl_by_phase: dict[str, float]
    blunder_rate: float
    best_move_agreement: float
    illegal_move_rate_raw: float
    retry_success_rate: float
    avg_tokens_per_move: float
    avg_cost_per_game: float
    p95_move_latency_ms: float
    timeout_rate: float
    total_cost_usd: float
    budget_cap_usd: float | None
    budget_utilization: float | None
    stopped_due_to_budget: bool
    budget_stop_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
