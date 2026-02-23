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

ALLOWED_PROTOCOL_MODES = {"direct", "agentic_compat", "research_strict"}
ALLOWED_BOARD_FORMATS = {"fen", "ascii", "combined", "unicode"}
ALLOWED_FEEDBACK_LEVELS = {"minimal", "moderate", "rich"}
ALLOWED_PLAYER_TYPES = {"random", "llm", "engine"}
ALLOWED_PLAYER_COLORS = {"white", "black"}
ALLOWED_EVAL_PLAYER_COLORS = {"white", "black", "auto"}
ALLOWED_TIMEOUT_POLICY_ACTIONS = {"stop_run"}
ALLOWED_RAG_SOURCES = {"eco", "lichess", "endgames"}
ALLOWED_FEW_SHOT_SOURCES = {"builtin", "config"}
ALLOWED_MULTI_AGENT_MODES = {"capability_moa", "specialist_moa", "hybrid_phase_router"}
ALLOWED_MULTI_AGENT_PROVIDER_POLICIES = {"shared_model", "role_model_overrides"}


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
            uci_limit_strength = player.get("uci_limit_strength")
            if uci_limit_strength is not None and not isinstance(uci_limit_strength, bool):
                raise ConfigValidationError(
                    f"players.{color}.uci_limit_strength must be a boolean when provided"
                )
            uci_elo = player.get("uci_elo")
            if uci_elo is not None and (not isinstance(uci_elo, int) or uci_elo <= 0):
                raise ConfigValidationError(f"players.{color}.uci_elo must be a positive int")
            if uci_elo is not None and uci_limit_strength is False:
                raise ConfigValidationError(
                    f"players.{color}.uci_limit_strength must be true when uci_elo is set"
                )
            skill_level = player.get("skill_level")
            if skill_level is not None and (
                not isinstance(skill_level, int) or skill_level < 0 or skill_level > 20
            ):
                raise ConfigValidationError(
                    f"players.{color}.skill_level must be an int in [0, 20]"
                )


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

    player_color = auto_cfg.get("player_color", "auto")
    if player_color not in ALLOWED_EVAL_PLAYER_COLORS:
        allowed = ", ".join(sorted(ALLOWED_EVAL_PLAYER_COLORS))
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


def _validate_strategy_rag(config: dict[str, Any]) -> None:
    rag_cfg = config.get("strategy", {}).get("rag")
    if rag_cfg is None:
        return
    if not isinstance(rag_cfg, dict):
        raise ConfigValidationError("strategy.rag must be a mapping when provided")

    enabled = rag_cfg.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigValidationError("strategy.rag.enabled must be a boolean")

    max_chunks = rag_cfg.get("max_chunks", 3)
    if not isinstance(max_chunks, int) or max_chunks <= 0:
        raise ConfigValidationError("strategy.rag.max_chunks must be a positive int")

    max_chars_per_chunk = rag_cfg.get("max_chars_per_chunk", 260)
    if not isinstance(max_chars_per_chunk, int) or max_chars_per_chunk <= 0:
        raise ConfigValidationError("strategy.rag.max_chars_per_chunk must be a positive int")

    min_similarity = rag_cfg.get("min_similarity", 0.08)
    if (
        not isinstance(min_similarity, (int, float))
        or min_similarity < 0
        or min_similarity > 1
    ):
        raise ConfigValidationError("strategy.rag.min_similarity must be in [0, 1]")

    enabled_sources = set(ALLOWED_RAG_SOURCES)

    sources = rag_cfg.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            raise ConfigValidationError("strategy.rag.sources must be a list when provided")
        source_values: set[str] = set()
        for item in sources:
            if not isinstance(item, str):
                raise ConfigValidationError("strategy.rag.sources entries must be strings")
            key = item.strip().lower()
            if key not in ALLOWED_RAG_SOURCES:
                allowed = ", ".join(sorted(ALLOWED_RAG_SOURCES))
                raise ConfigValidationError(f"strategy.rag.sources entries must be one of [{allowed}]")
            source_values.add(key)
        if source_values:
            enabled_sources = source_values

    include_sources = rag_cfg.get("include_sources")
    if include_sources is not None:
        if not isinstance(include_sources, dict):
            raise ConfigValidationError("strategy.rag.include_sources must be a mapping when provided")
        for source_name, enabled_flag in include_sources.items():
            if not isinstance(source_name, str):
                raise ConfigValidationError(
                    "strategy.rag.include_sources keys must be source names"
                )
            key = source_name.strip().lower()
            if key not in ALLOWED_RAG_SOURCES:
                allowed = ", ".join(sorted(ALLOWED_RAG_SOURCES))
                raise ConfigValidationError(
                    f"strategy.rag.include_sources keys must be one of [{allowed}]"
                )
            if not isinstance(enabled_flag, bool):
                raise ConfigValidationError(
                    f"strategy.rag.include_sources.{key} must be boolean"
                )
            if enabled_flag:
                enabled_sources.add(key)
            else:
                enabled_sources.discard(key)

    if enabled and not enabled_sources:
        raise ConfigValidationError(
            "strategy.rag must enable at least one source when strategy.rag.enabled=true"
        )


def _validate_strategy_few_shot(config: dict[str, Any]) -> None:
    few_shot_cfg = config.get("strategy", {}).get("few_shot")
    if few_shot_cfg is None:
        return
    if not isinstance(few_shot_cfg, dict):
        raise ConfigValidationError("strategy.few_shot must be a mapping when provided")

    enabled = few_shot_cfg.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigValidationError("strategy.few_shot.enabled must be a boolean")

    source = few_shot_cfg.get("source", "builtin")
    if not isinstance(source, str) or source.strip().lower() not in ALLOWED_FEW_SHOT_SOURCES:
        allowed = ", ".join(sorted(ALLOWED_FEW_SHOT_SOURCES))
        raise ConfigValidationError(f"strategy.few_shot.source must be one of [{allowed}]")

    max_examples = few_shot_cfg.get("max_examples")
    if max_examples is not None and (not isinstance(max_examples, int) or max_examples <= 0):
        raise ConfigValidationError(
            "strategy.few_shot.max_examples must be a positive int when provided"
        )

    by_phase = few_shot_cfg.get("by_phase")
    if by_phase is not None:
        if not isinstance(by_phase, dict):
            raise ConfigValidationError("strategy.few_shot.by_phase must be a mapping when provided")
        for phase_name, entries in by_phase.items():
            if not isinstance(phase_name, str) or not phase_name.strip():
                raise ConfigValidationError(
                    "strategy.few_shot.by_phase keys must be non-empty strings"
                )
            if not isinstance(entries, list):
                raise ConfigValidationError(
                    f"strategy.few_shot.by_phase.{phase_name} must be a list of examples"
                )

    if enabled and source.strip().lower() == "config" and (
        not isinstance(by_phase, dict) or not by_phase
    ):
        raise ConfigValidationError(
            "strategy.few_shot.by_phase must be defined when strategy.few_shot.source=config and enabled=true"
        )


def _validate_strategy_multi_agent(config: dict[str, Any]) -> None:
    multi_agent_cfg = config.get("strategy", {}).get("multi_agent")
    if multi_agent_cfg is None:
        return
    if not isinstance(multi_agent_cfg, dict):
        raise ConfigValidationError("strategy.multi_agent must be a mapping when provided")

    enabled = multi_agent_cfg.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigValidationError("strategy.multi_agent.enabled must be a boolean")

    mode = multi_agent_cfg.get("mode", "capability_moa")
    if not isinstance(mode, str) or mode.strip().lower() not in ALLOWED_MULTI_AGENT_MODES:
        allowed = ", ".join(sorted(ALLOWED_MULTI_AGENT_MODES))
        raise ConfigValidationError(f"strategy.multi_agent.mode must be one of [{allowed}]")

    proposer_count = multi_agent_cfg.get("proposer_count", 2)
    if not isinstance(proposer_count, int) or proposer_count <= 0:
        raise ConfigValidationError("strategy.multi_agent.proposer_count must be a positive int")

    include_legal = multi_agent_cfg.get("include_legal_moves_in_aggregator", True)
    if not isinstance(include_legal, bool):
        raise ConfigValidationError(
            "strategy.multi_agent.include_legal_moves_in_aggregator must be a boolean"
        )

    proposer_roles = multi_agent_cfg.get("proposer_roles")
    if proposer_roles is not None:
        if not isinstance(proposer_roles, list):
            raise ConfigValidationError("strategy.multi_agent.proposer_roles must be a list")
        for role in proposer_roles:
            if not isinstance(role, str) or not role.strip():
                raise ConfigValidationError(
                    "strategy.multi_agent.proposer_roles entries must be non-empty strings"
                )

    provider_policy = multi_agent_cfg.get("provider_policy", "shared_model")
    if (
        not isinstance(provider_policy, str)
        or provider_policy.strip().lower() not in ALLOWED_MULTI_AGENT_PROVIDER_POLICIES
    ):
        allowed = ", ".join(sorted(ALLOWED_MULTI_AGENT_PROVIDER_POLICIES))
        raise ConfigValidationError(
            f"strategy.multi_agent.provider_policy must be one of [{allowed}]"
        )

    role_models = multi_agent_cfg.get("role_models")
    if role_models is not None:
        if not isinstance(role_models, dict):
            raise ConfigValidationError("strategy.multi_agent.role_models must be a mapping")
        for role, model in role_models.items():
            if not isinstance(role, str) or not role.strip():
                raise ConfigValidationError(
                    "strategy.multi_agent.role_models keys must be non-empty strings"
                )
            if not isinstance(model, str) or not model.strip():
                raise ConfigValidationError(
                    "strategy.multi_agent.role_models values must be non-empty strings"
                )

    if enabled and proposer_count > 8:
        raise ConfigValidationError("strategy.multi_agent.proposer_count must be <= 8")


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

    use_system_prompt = config.get("strategy", {}).get("use_system_prompt")
    if use_system_prompt is not None and not isinstance(use_system_prompt, bool):
        raise ConfigValidationError("strategy.use_system_prompt must be a boolean when provided")
    system_prompt_id = config.get("strategy", {}).get("system_prompt_id", "default")
    if not isinstance(system_prompt_id, str) or not system_prompt_id.strip():
        raise ConfigValidationError("strategy.system_prompt_id must be a non-empty string")
    system_prompt_template = config.get("strategy", {}).get("system_prompt_template")
    if system_prompt_template is not None and (
        not isinstance(system_prompt_template, str) or not system_prompt_template.strip()
    ):
        raise ConfigValidationError(
            "strategy.system_prompt_template must be a non-empty string when provided"
        )

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

    persist_prompt_transcripts = config.get("tracking", {}).get("persist_prompt_transcripts")
    if persist_prompt_transcripts is not None and not isinstance(
        persist_prompt_transcripts, bool
    ):
        raise ConfigValidationError(
            "tracking.persist_prompt_transcripts must be a boolean when provided"
        )

    _validate_player_config(_get_by_path(config, "players"))
    _validate_evaluation_auto(config)
    _validate_timeout_policy(config)
    _validate_strategy_rag(config)
    _validate_strategy_few_shot(config)
    _validate_strategy_multi_agent(config)
