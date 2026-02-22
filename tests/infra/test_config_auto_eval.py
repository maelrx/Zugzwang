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
