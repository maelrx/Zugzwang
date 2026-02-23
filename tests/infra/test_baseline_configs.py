from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]
BASELINES = [
    "random_legal.yaml",
    "stockfish_elo_800.yaml",
    "stockfish_elo_1200.yaml",
    "stockfish_elo_1600.yaml",
    "stockfish_elo_2000.yaml",
    "llm_mirror.yaml",
]


@pytest.mark.parametrize("baseline_name", BASELINES)
def test_m2_baseline_configs_resolve_and_validate(baseline_name: str) -> None:
    config_path = ROOT / "configs" / "baselines" / baseline_name
    resolved, cfg_hash = resolve_with_hash(config_path)

    assert isinstance(resolved, dict)
    assert len(cfg_hash) == 64
    assert resolved["experiment"]["target_valid_games"] > 0
    assert resolved["budget"]["max_total_usd"] > 0
    assert resolved["evaluation"]["auto"]["enabled"] is True
    assert resolved["evaluation"]["auto"]["player_color"] == "auto"


@pytest.mark.parametrize(
    ("baseline_name", "expected_elo"),
    [
        ("stockfish_elo_800.yaml", 800),
        ("stockfish_elo_1200.yaml", 1200),
        ("stockfish_elo_1600.yaml", 1600),
        ("stockfish_elo_2000.yaml", 2000),
    ],
)
def test_stockfish_elo_baselines_are_consistent(
    baseline_name: str,
    expected_elo: int,
) -> None:
    config_path = ROOT / "configs" / "baselines" / baseline_name
    resolved, _ = resolve_with_hash(config_path)

    black = resolved["players"]["black"]
    assert black["type"] == "engine"
    assert black["uci_limit_strength"] is True
    assert black["uci_elo"] == expected_elo
    assert resolved["evaluation"]["auto"]["opponent_elo"] == expected_elo


def test_baseline_config_hash_is_reproducible_for_same_file() -> None:
    config_path = ROOT / "configs" / "baselines" / "llm_mirror.yaml"
    _, hash_a = resolve_with_hash(config_path)
    _, hash_b = resolve_with_hash(config_path)

    assert hash_a == hash_b
