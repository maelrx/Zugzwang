from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zugzwang.core.game import play_game
from zugzwang.core.models import GameRecord
from zugzwang.core.players import build_player
from zugzwang.evaluation.pipeline import evaluate_run_dir
from zugzwang.evaluation.metrics import summarize_experiment
from zugzwang.experiments.resume import (
    count_valid_games,
    resolve_resume_state,
)
from zugzwang.experiments.tracker import (
    ensure_run_dirs,
    write_experiment_report,
    write_game_record,
    write_run_metadata,
    write_resolved_config,
)
from zugzwang.infra.config import resolve_with_hash
from zugzwang.infra.env import PROVIDER_ENV_KEYS, validate_environment
from zugzwang.infra.ids import game_seed, make_run_id, timestamp_utc

NON_VALID_TERMINATIONS = {"error", "timeout", "provider_failure"}


@dataclass
class PreparedRun:
    config: dict[str, Any]
    config_hash: str
    run_id: str
    scheduled_games: int
    estimated_total_cost_usd: float | None


@dataclass
class TimeoutPolicy:
    enabled: bool
    min_games_before_enforcement: int
    max_provider_timeout_game_rate: float
    min_observed_completion_rate: float
    action: str


class ExperimentRunner:
    def __init__(
        self,
        config_path: str | Path,
        model_profile_path: str | Path | None = None,
        overrides: list[str] | None = None,
        resume: bool = False,
        resume_run_id: str | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.model_profile_path = Path(model_profile_path) if model_profile_path else None
        self.overrides = overrides or []
        self.resume = resume
        self.resume_run_id = resume_run_id

    def prepare(self) -> PreparedRun:
        resolved, cfg_hash = resolve_with_hash(
            experiment_config_path=self.config_path,
            model_profile_path=self.model_profile_path,
            cli_overrides=self.overrides,
        )
        experiment_name = resolved["experiment"]["name"]
        run_id = make_run_id(experiment_name, cfg_hash)
        target_valid = int(resolved["experiment"]["target_valid_games"])
        expected_completion = float(resolved["runtime"].get("expected_completion_rate", 1.0))
        scheduled_games = math.ceil(target_valid / expected_completion)
        max_games = int(resolved["experiment"].get("max_games", scheduled_games))
        scheduled_games = min(scheduled_games, max_games)
        estimated_avg_cost = float(resolved.get("budget", {}).get("estimated_avg_cost_per_game_usd", 0.0))
        estimated_total_cost_usd = None
        if estimated_avg_cost > 0:
            estimated_total_cost_usd = estimated_avg_cost * scheduled_games
        return PreparedRun(
            config=resolved,
            config_hash=cfg_hash,
            run_id=run_id,
            scheduled_games=scheduled_games,
            estimated_total_cost_usd=estimated_total_cost_usd,
        )

    def dry_run(self) -> dict[str, Any]:
        prepared = self.prepare()
        run_output = prepared.config["runtime"].get("output_dir", "results/runs")
        resume_state = resolve_resume_state(
            output_root=run_output,
            experiment_name=str(prepared.config["experiment"]["name"]),
            config_hash=prepared.config_hash,
            generated_run_id=prepared.run_id,
            resume=self.resume,
            resume_run_id=self.resume_run_id,
        )
        return {
            "config_path": str(self.config_path),
            "config_hash": prepared.config_hash,
            "run_id": resume_state.run_id,
            "scheduled_games": prepared.scheduled_games,
            "estimated_total_cost_usd": prepared.estimated_total_cost_usd,
            "resume": {
                "enabled": self.resume,
                "requested_run_id": self.resume_run_id,
                "resumed": resume_state.resumed,
                "existing_games_loaded": resume_state.existing_games,
                "existing_valid_games": resume_state.existing_valid_games,
            },
            "resolved_config": prepared.config,
        }

    def run(self) -> dict[str, Any]:
        prepared = self.prepare()
        config = prepared.config
        validate_environment(config)

        run_output = config["runtime"].get("output_dir", "results/runs")
        resume_state = resolve_resume_state(
            output_root=run_output,
            experiment_name=str(config["experiment"]["name"]),
            config_hash=prepared.config_hash,
            generated_run_id=prepared.run_id,
            resume=self.resume,
            resume_run_id=self.resume_run_id,
        )
        run_dir = ensure_run_dirs(run_output, resume_state.run_id)
        write_resolved_config(run_dir, config, prepared.config_hash)
        metadata_path = write_run_metadata(
            run_dir,
            self._build_run_metadata(
                prepared=prepared,
                run_id=resume_state.run_id,
                run_dir=run_dir,
                resumed=resume_state.resumed,
                existing_games=resume_state.existing_games,
                existing_valid_games=resume_state.existing_valid_games,
            ),
        )

        target_valid = int(config["experiment"]["target_valid_games"])
        base_seed = int(config["runtime"].get("seed", 42))
        max_plies = int(config["runtime"].get("max_plies", 200))
        protocol_mode = str(config["protocol"]["mode"])
        strategy_cfg = config["strategy"]
        budget_cap_usd = float(config["budget"]["max_total_usd"])
        estimated_avg_cost = float(config["budget"].get("estimated_avg_cost_per_game_usd", 0.0))
        timeout_policy = _timeout_policy_from_config(config)

        records = list(resume_state.existing_records)
        valid_games = count_valid_games(records)
        total_cost_usd = float(sum(record.cost_usd for record in records))
        stopped_due_to_budget = False
        budget_stop_reason: str | None = None
        stopped_due_to_reliability = False
        reliability_stop_reason: str | None = None

        for game_number in range(resume_state.next_game_number, prepared.scheduled_games + 1):
            if valid_games >= target_valid:
                break

            remaining_games = prepared.scheduled_games - len(records)
            observed_avg_cost = (total_cost_usd / len(records)) if records else 0.0
            projection_rate = max(estimated_avg_cost, observed_avg_cost)
            projected_total_cost = total_cost_usd + (projection_rate * remaining_games)

            if total_cost_usd >= budget_cap_usd:
                stopped_due_to_budget = True
                budget_stop_reason = "budget_cap_reached"
                break
            if projection_rate > 0 and projected_total_cost > budget_cap_usd:
                stopped_due_to_budget = True
                budget_stop_reason = "projected_budget_exceeded"
                break

            seed = game_seed(base_seed, game_number)
            rng = random.Random(seed)

            white_cfg = config["players"]["white"]
            black_cfg = config["players"]["black"]
            white_player = build_player(white_cfg, protocol_mode, strategy_cfg, rng)
            black_player = build_player(black_cfg, protocol_mode, strategy_cfg, rng)

            record = play_game(
                experiment_id=resume_state.run_id,
                game_number=game_number,
                config_hash=prepared.config_hash,
                seed=seed,
                players_cfg=config["players"],
                white_player=white_player,
                black_player=black_player,
                max_plies=max_plies,
            )
            write_game_record(run_dir, record)
            records.append(record)
            total_cost_usd += record.cost_usd

            if record.termination not in NON_VALID_TERMINATIONS:
                valid_games += 1
            if _should_stop_for_reliability(
                records=records,
                valid_games=valid_games,
                timeout_policy=timeout_policy,
            ):
                stopped_due_to_reliability = True
                if _provider_timeout_game_rate(records) > timeout_policy.max_provider_timeout_game_rate:
                    reliability_stop_reason = "provider_timeout_rate_exceeded"
                else:
                    reliability_stop_reason = "completion_rate_below_threshold"
                break
            if valid_games >= target_valid:
                break

        report = summarize_experiment(
            experiment_id=resume_state.run_id,
            config_hash=prepared.config_hash,
            target_games=target_valid,
            scheduled_games=prepared.scheduled_games,
            game_records=records,
            budget_cap_usd=budget_cap_usd,
            stopped_due_to_budget=stopped_due_to_budget,
            budget_stop_reason=budget_stop_reason,
            stopped_due_to_reliability=stopped_due_to_reliability,
            reliability_stop_reason=reliability_stop_reason,
        )
        write_experiment_report(run_dir, report)
        evaluation_summary = self._maybe_auto_evaluate(
            config=config,
            run_dir=run_dir,
            games_written=len(records),
        )

        return {
            "run_id": resume_state.run_id,
            "config_hash": prepared.config_hash,
            "run_dir": str(run_dir),
            "run_metadata": str(metadata_path),
            "resumed": resume_state.resumed,
            "existing_games_loaded": resume_state.existing_games,
            "games_written": len(records),
            "valid_games": report.num_games_valid,
            "total_cost_usd": report.total_cost_usd,
            "budget_cap_usd": budget_cap_usd,
            "stopped_due_to_budget": stopped_due_to_budget,
            "budget_stop_reason": budget_stop_reason,
            "stopped_due_to_reliability": stopped_due_to_reliability,
            "reliability_stop_reason": reliability_stop_reason,
            "provider_timeout_game_rate": report.provider_timeout_game_rate,
            "nonvalid_game_rate": report.nonvalid_game_rate,
            "evaluation": evaluation_summary,
        }

    def _build_run_metadata(
        self,
        prepared: PreparedRun,
        run_id: str,
        run_dir: Path,
        resumed: bool,
        existing_games: int,
        existing_valid_games: int,
    ) -> dict[str, Any]:
        return {
            "created_at_utc": timestamp_utc(),
            "run_id": run_id,
            "config_hash": prepared.config_hash,
            "paths": {
                "run_dir": str(run_dir),
                "config_path": str(self.config_path),
                "model_profile_path": str(self.model_profile_path)
                if self.model_profile_path
                else None,
            },
            "overrides": list(self.overrides),
            "scheduled_games": prepared.scheduled_games,
            "estimated_total_cost_usd": prepared.estimated_total_cost_usd,
            "resume": {
                "enabled": self.resume,
                "requested_run_id": self.resume_run_id,
                "resumed": resumed,
                "existing_games_loaded": existing_games,
                "existing_valid_games": existing_valid_games,
            },
            "runtime_guardrails": {
                "timeout_policy": prepared.config.get("runtime", {}).get("timeout_policy", {}),
            },
            "required_env_vars": self._required_env_vars(prepared.config),
            "resolved_config": prepared.config,
        }

    @staticmethod
    def _required_env_vars(config: dict[str, Any]) -> list[str]:
        values: set[str] = set()
        players = config.get("players", {})
        for color in ("white", "black"):
            player = players.get(color)
            if not isinstance(player, dict) or player.get("type") != "llm":
                continue
            provider = str(player.get("provider", "")).lower()
            env_keys = PROVIDER_ENV_KEYS.get(provider)
            if env_keys:
                values.update(env_keys)
        return sorted(values)

    def _maybe_auto_evaluate(
        self,
        config: dict[str, Any],
        run_dir: Path,
        games_written: int,
    ) -> dict[str, Any]:
        evaluation_cfg = config.get("evaluation", {})
        if not isinstance(evaluation_cfg, dict):
            return {"enabled": False, "status": "skipped", "reason": "missing_evaluation_config"}

        auto_cfg = evaluation_cfg.get("auto", {})
        if not isinstance(auto_cfg, dict):
            return {"enabled": False, "status": "skipped", "reason": "invalid_auto_config"}

        enabled = bool(auto_cfg.get("enabled", False))
        if not enabled:
            return {"enabled": False, "status": "skipped", "reason": "disabled"}
        if games_written <= 0:
            return {"enabled": True, "status": "skipped", "reason": "no_games_to_evaluate"}

        player_color = str(auto_cfg.get("player_color", "black"))
        opponent_elo_raw = auto_cfg.get("opponent_elo")
        opponent_elo = float(opponent_elo_raw) if opponent_elo_raw is not None else None
        elo_color_correction = float(auto_cfg.get("elo_color_correction", 0.0))
        output_filename = str(
            auto_cfg.get("output_filename", "experiment_report_evaluated.json")
        )
        fail_on_error = bool(auto_cfg.get("fail_on_error", False))

        try:
            payload = evaluate_run_dir(
                run_dir=run_dir,
                player_color=player_color,
                opponent_elo=opponent_elo,
                elo_color_correction=elo_color_correction,
                output_filename=output_filename,
            )
        except Exception as exc:
            if fail_on_error:
                raise
            return {
                "enabled": True,
                "status": "failed",
                "error": str(exc),
            }

        return {
            "enabled": True,
            "status": "completed",
            "output_report": payload.get("output_report"),
            "payload": payload,
        }


def _timeout_policy_from_config(config: dict[str, Any]) -> TimeoutPolicy:
    runtime_cfg = config.get("runtime", {})
    timeout_policy_cfg = runtime_cfg.get("timeout_policy", {})
    if not isinstance(timeout_policy_cfg, dict):
        timeout_policy_cfg = {}
    return TimeoutPolicy(
        enabled=bool(timeout_policy_cfg.get("enabled", False)),
        min_games_before_enforcement=int(timeout_policy_cfg.get("min_games_before_enforcement", 5)),
        max_provider_timeout_game_rate=float(
            timeout_policy_cfg.get("max_provider_timeout_game_rate", 0.25)
        ),
        min_observed_completion_rate=float(
            timeout_policy_cfg.get("min_observed_completion_rate", 0.6)
        ),
        action=str(timeout_policy_cfg.get("action", "stop_run")),
    )


def _should_stop_for_reliability(
    records: list[GameRecord],
    valid_games: int,
    timeout_policy: TimeoutPolicy,
) -> bool:
    if not timeout_policy.enabled:
        return False
    if timeout_policy.action != "stop_run":
        return False
    if len(records) < timeout_policy.min_games_before_enforcement:
        return False

    timeout_rate = _provider_timeout_game_rate(records)
    if timeout_rate > timeout_policy.max_provider_timeout_game_rate:
        return True

    observed_completion_rate = (valid_games / len(records)) if records else 0.0
    if observed_completion_rate < timeout_policy.min_observed_completion_rate:
        return True
    return False


def _provider_timeout_game_rate(records: list[GameRecord]) -> float:
    if not records:
        return 0.0
    timeout_games = sum(1 for record in records if _record_has_provider_timeout(record))
    return timeout_games / len(records)


def _record_has_provider_timeout(record: GameRecord) -> bool:
    for move in record.moves:
        error = move.move_decision.error
        if isinstance(error, str) and error.startswith("provider_timeout"):
            return True
    return False
