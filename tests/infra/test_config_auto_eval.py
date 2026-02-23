from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.infra.config import resolve_config


ROOT = Path(__file__).resolve().parents[2]


def test_config_accepts_evaluation_auto_block() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "evaluation.auto.enabled=true",
            "evaluation.auto.player_color=white",
            "evaluation.auto.opponent_elo=1400",
            "evaluation.auto.output_filename=custom_eval.json",
        ],
    )
    assert resolved["evaluation"]["auto"]["enabled"] is True
    assert resolved["evaluation"]["auto"]["player_color"] == "white"


def test_config_rejects_invalid_evaluation_auto_player_color() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    with pytest.raises(ValueError, match="evaluation.auto.player_color"):
        resolve_config(
            experiment_config_path=config_path,
            cli_overrides=["evaluation.auto.player_color=green"],
        )


def test_config_accepts_runtime_timeout_policy_block() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "runtime.timeout_policy.enabled=true",
            "runtime.timeout_policy.min_games_before_enforcement=3",
            "runtime.timeout_policy.max_provider_timeout_game_rate=0.4",
            "runtime.timeout_policy.min_observed_completion_rate=0.7",
            "runtime.timeout_policy.action=stop_run",
        ],
    )
    policy = resolved["runtime"]["timeout_policy"]
    assert policy["enabled"] is True
    assert policy["min_games_before_enforcement"] == 3


def test_config_rejects_invalid_timeout_policy_rate() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    with pytest.raises(ValueError, match="runtime.timeout_policy.max_provider_timeout_game_rate"):
        resolve_config(
            experiment_config_path=config_path,
            cli_overrides=["runtime.timeout_policy.max_provider_timeout_game_rate=1.5"],
        )


def test_config_accepts_strategy_rag_block() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "strategy.rag.enabled=true",
            "strategy.rag.max_chunks=2",
            "strategy.rag.max_chars_per_chunk=180",
            "strategy.rag.min_similarity=0.12",
            "strategy.rag.include_sources.eco=true",
            "strategy.rag.include_sources.lichess=false",
            "strategy.rag.include_sources.endgames=true",
        ],
    )
    rag = resolved["strategy"]["rag"]
    assert rag["enabled"] is True
    assert rag["max_chunks"] == 2


def test_config_rejects_invalid_strategy_rag_source() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    with pytest.raises(ValueError, match="strategy.rag.include_sources keys"):
        resolve_config(
            experiment_config_path=config_path,
            cli_overrides=["strategy.rag.include_sources.unknown=true"],
        )


def test_config_accepts_strategy_multi_agent_block() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "strategy.multi_agent.enabled=true",
            "strategy.multi_agent.mode=capability_moa",
            "strategy.multi_agent.proposer_count=2",
            "strategy.multi_agent.include_legal_moves_in_aggregator=true",
        ],
    )
    cfg = resolved["strategy"]["multi_agent"]
    assert cfg["enabled"] is True
    assert cfg["mode"] == "capability_moa"


def test_config_accepts_strategy_multi_agent_specialist_mode() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "strategy.multi_agent.enabled=true",
            "strategy.multi_agent.mode=specialist_moa",
            "strategy.multi_agent.proposer_count=3",
        ],
    )
    cfg = resolved["strategy"]["multi_agent"]
    assert cfg["mode"] == "specialist_moa"


def test_config_accepts_strategy_multi_agent_hybrid_with_role_model_overrides() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "strategy.multi_agent.enabled=true",
            "strategy.multi_agent.mode=hybrid_phase_router",
            "strategy.multi_agent.provider_policy=role_model_overrides",
            "strategy.multi_agent.role_models.tactical=mock-tactical",
            "strategy.multi_agent.role_models.aggregator=mock-aggregator",
        ],
    )
    cfg = resolved["strategy"]["multi_agent"]
    assert cfg["mode"] == "hybrid_phase_router"
    assert cfg["provider_policy"] == "role_model_overrides"
    assert cfg["role_models"]["aggregator"] == "mock-aggregator"


def test_config_rejects_invalid_strategy_multi_agent_mode() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    with pytest.raises(ValueError, match="strategy.multi_agent.mode"):
        resolve_config(
            experiment_config_path=config_path,
            cli_overrides=["strategy.multi_agent.mode=unknown_mode"],
        )


def test_config_rejects_invalid_strategy_multi_agent_provider_policy() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    with pytest.raises(ValueError, match="strategy.multi_agent.provider_policy"):
        resolve_config(
            experiment_config_path=config_path,
            cli_overrides=["strategy.multi_agent.provider_policy=invalid_policy"],
        )


def test_config_accepts_engine_native_uci_elo() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    resolved = resolve_config(
        experiment_config_path=config_path,
        cli_overrides=[
            "players.white.type=engine",
            "players.white.uci_limit_strength=true",
            "players.white.uci_elo=1200",
        ],
    )
    white_player = resolved["players"]["white"]
    assert white_player["type"] == "engine"
    assert white_player["uci_limit_strength"] is True
    assert white_player["uci_elo"] == 1200


def test_config_rejects_engine_uci_elo_without_limit_strength() -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    with pytest.raises(ValueError, match="players.white.uci_limit_strength"):
        resolve_config(
            experiment_config_path=config_path,
            cli_overrides=[
                "players.white.type=engine",
                "players.white.uci_limit_strength=false",
                "players.white.uci_elo=1200",
            ],
        )
