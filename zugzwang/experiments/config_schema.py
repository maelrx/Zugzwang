from __future__ import annotations

from typing import Any


class ConfigValidationError(ValueError):
    """Raised when resolved experiment config is invalid."""


REQUIRED_SECTIONS = [
    "experiment",
    "players",
    "protocol",
    "strategy",
    "evaluation",
    "runtime",
    "budget",
    "tracking",
]

REQUIRED_FIELDS = [
    "experiment.name",
    "experiment.target_valid_games",
    "players.white",
    "players.black",
    "protocol.mode",
    "strategy.board_format",
    "evaluation.stockfish.depth",
    "budget.max_total_usd",
]

ALLOWED_PROTOCOL_MODES = {"direct", "agentic_compat"}
ALLOWED_BOARD_FORMATS = {"fen", "ascii", "combined", "unicode"}
ALLOWED_FEEDBACK_LEVELS = {"minimal", "moderate", "rich"}
ALLOWED_PLAYER_TYPES = {"random", "llm", "engine"}
ALLOWED_PLAYER_COLORS = {"white", "black"}
ALLOWED_TIMEOUT_POLICY_ACTIONS = {"stop_run"}


def _get_by_path(config: dict[str, Any], path: str) -> Any:
    current: Any = config
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConfigValidationError(f"Missing required field: {path}")
        current = current[part]
    return current


def _validate_player_config(players: dict[str, Any]) -> None:
    for color in ("white", "black"):
        player = players[color]
        if not isinstance(player, dict):
            raise ConfigValidationError(f"players.{color} must be a mapping")
        player_type = player.get("type")
        if player_type not in ALLOWED_PLAYER_TYPES:
            allowed = ", ".join(sorted(ALLOWED_PLAYER_TYPES))
            raise ConfigValidationError(
                f"players.{color}.type must be one of [{allowed}]"
            )
        if player_type == "llm":
            if not player.get("provider"):
                raise ConfigValidationError(f"players.{color}.provider is required for llm")
            if not player.get("model"):
                raise ConfigValidationError(f"players.{color}.model is required for llm")
        if player_type == "engine":
            path = player.get("path")
            if path is not None and not isinstance(path, str):
                raise ConfigValidationError(f"players.{color}.path must be a string when provided")
            depth = player.get("depth", 8)
            if not isinstance(depth, int) or depth <= 0:
                raise ConfigValidationError(f"players.{color}.depth must be a positive int")
            movetime_ms = player.get("movetime_ms")
            if movetime_ms is not None and (
                not isinstance(movetime_ms, (int, float)) or movetime_ms <= 0
            ):
                raise ConfigValidationError(
                    f"players.{color}.movetime_ms must be a positive number when provided"
                )
            threads = player.get("threads", 1)
            if not isinstance(threads, int) or threads <= 0:
                raise ConfigValidationError(f"players.{color}.threads must be a positive int")
            hash_mb = player.get("hash_mb", 64)
            if not isinstance(hash_mb, int) or hash_mb <= 0:
                raise ConfigValidationError(f"players.{color}.hash_mb must be a positive int")


def _validate_evaluation_auto(config: dict[str, Any]) -> None:
    auto_cfg = config.get("evaluation", {}).get("auto")
    if auto_cfg is None:
        return
    if not isinstance(auto_cfg, dict):
        raise ConfigValidationError("evaluation.auto must be a mapping when provided")

    enabled = auto_cfg.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigValidationError("evaluation.auto.enabled must be a boolean")

    fail_on_error = auto_cfg.get("fail_on_error", False)
    if not isinstance(fail_on_error, bool):
        raise ConfigValidationError("evaluation.auto.fail_on_error must be a boolean")

    player_color = auto_cfg.get("player_color", "black")
    if player_color not in ALLOWED_PLAYER_COLORS:
        allowed = ", ".join(sorted(ALLOWED_PLAYER_COLORS))
        raise ConfigValidationError(f"evaluation.auto.player_color must be one of [{allowed}]")

    opponent_elo = auto_cfg.get("opponent_elo")
    if opponent_elo is not None and not isinstance(opponent_elo, (int, float)):
        raise ConfigValidationError("evaluation.auto.opponent_elo must be numeric or null")

    elo_correction = auto_cfg.get("elo_color_correction", 0.0)
    if not isinstance(elo_correction, (int, float)):
        raise ConfigValidationError("evaluation.auto.elo_color_correction must be numeric")

    output_filename = auto_cfg.get("output_filename", "experiment_report_evaluated.json")
    if not isinstance(output_filename, str) or not output_filename.strip():
        raise ConfigValidationError("evaluation.auto.output_filename must be a non-empty string")


def _validate_timeout_policy(config: dict[str, Any]) -> None:
    timeout_policy = config.get("runtime", {}).get("timeout_policy")
    if timeout_policy is None:
        return
    if not isinstance(timeout_policy, dict):
        raise ConfigValidationError("runtime.timeout_policy must be a mapping when provided")

    enabled = timeout_policy.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigValidationError("runtime.timeout_policy.enabled must be a boolean")

    min_games = timeout_policy.get("min_games_before_enforcement", 5)
    if not isinstance(min_games, int) or min_games <= 0:
        raise ConfigValidationError(
            "runtime.timeout_policy.min_games_before_enforcement must be a positive int"
        )

    max_timeout_rate = timeout_policy.get("max_provider_timeout_game_rate", 0.25)
    if (
        not isinstance(max_timeout_rate, (int, float))
        or max_timeout_rate < 0
        or max_timeout_rate > 1
    ):
        raise ConfigValidationError(
            "runtime.timeout_policy.max_provider_timeout_game_rate must be in [0, 1]"
        )

    min_completion = timeout_policy.get("min_observed_completion_rate", 0.6)
    if (
        not isinstance(min_completion, (int, float))
        or min_completion < 0
        or min_completion > 1
    ):
        raise ConfigValidationError(
            "runtime.timeout_policy.min_observed_completion_rate must be in [0, 1]"
        )

    action = timeout_policy.get("action", "stop_run")
    if action not in ALLOWED_TIMEOUT_POLICY_ACTIONS:
        allowed = ", ".join(sorted(ALLOWED_TIMEOUT_POLICY_ACTIONS))
        raise ConfigValidationError(f"runtime.timeout_policy.action must be one of [{allowed}]")


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ConfigValidationError("Resolved config must be a mapping")

    for section in REQUIRED_SECTIONS:
        if section not in config:
            raise ConfigValidationError(f"Missing required config section: {section}")

    for path in REQUIRED_FIELDS:
        _get_by_path(config, path)

    mode = _get_by_path(config, "protocol.mode")
    if mode not in ALLOWED_PROTOCOL_MODES:
        allowed = ", ".join(sorted(ALLOWED_PROTOCOL_MODES))
        raise ConfigValidationError(f"protocol.mode must be one of [{allowed}]")

    board_format = _get_by_path(config, "strategy.board_format")
    if board_format not in ALLOWED_BOARD_FORMATS:
        allowed = ", ".join(sorted(ALLOWED_BOARD_FORMATS))
        raise ConfigValidationError(f"strategy.board_format must be one of [{allowed}]")

    feedback = config.get("strategy", {}).get("validation", {}).get("feedback_level", "rich")
    if feedback not in ALLOWED_FEEDBACK_LEVELS:
        allowed = ", ".join(sorted(ALLOWED_FEEDBACK_LEVELS))
        raise ConfigValidationError(
            f"strategy.validation.feedback_level must be one of [{allowed}]"
        )

    target_games = _get_by_path(config, "experiment.target_valid_games")
    if not isinstance(target_games, int) or target_games <= 0:
        raise ConfigValidationError("experiment.target_valid_games must be a positive int")

    depth = _get_by_path(config, "evaluation.stockfish.depth")
    if not isinstance(depth, int) or depth <= 0:
        raise ConfigValidationError("evaluation.stockfish.depth must be a positive int")
    threads = config.get("evaluation", {}).get("stockfish", {}).get("threads", 1)
    if not isinstance(threads, int) or threads <= 0:
        raise ConfigValidationError("evaluation.stockfish.threads must be a positive int")
    hash_mb = config.get("evaluation", {}).get("stockfish", {}).get("hash_mb", 128)
    if not isinstance(hash_mb, int) or hash_mb <= 0:
        raise ConfigValidationError("evaluation.stockfish.hash_mb must be a positive int")

    completion_rate = config.get("runtime", {}).get("expected_completion_rate", 1.0)
    if not isinstance(completion_rate, (int, float)) or completion_rate <= 0 or completion_rate > 1:
        raise ConfigValidationError(
            "runtime.expected_completion_rate must be a float in (0, 1]"
        )

    budget_cap = _get_by_path(config, "budget.max_total_usd")
    if not isinstance(budget_cap, (int, float)) or budget_cap <= 0:
        raise ConfigValidationError("budget.max_total_usd must be a positive number")
    estimated_avg_cost = config.get("budget", {}).get("estimated_avg_cost_per_game_usd", 0.0)
    if not isinstance(estimated_avg_cost, (int, float)) or estimated_avg_cost < 0:
        raise ConfigValidationError(
            "budget.estimated_avg_cost_per_game_usd must be a non-negative number"
        )

    _validate_player_config(_get_by_path(config, "players"))
    _validate_evaluation_auto(config)
    _validate_timeout_policy(config)
