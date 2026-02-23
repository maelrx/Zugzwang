from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "filename",
    [
        "transferability_single_agent_template.yaml",
        "transferability_moa_template.yaml",
        "transferability_moa_role_overrides_template.yaml",
    ],
)
def test_transferability_templates_resolve_and_enforce_operational_guards(
    filename: str,
) -> None:
    config_path = ROOT / "configs" / "ablations" / filename
    resolved, cfg_hash = resolve_with_hash(config_path)

    assert len(cfg_hash) == 64
    assert resolved["protocol"]["mode"] == "research_strict"
    assert resolved["evaluation"]["auto"]["enabled"] is True

    black_player = resolved["players"]["black"]
    assert black_player["type"] == "llm"
    assert isinstance(black_player["provider"], str) and black_player["provider"].strip()
    assert isinstance(black_player["model"], str) and black_player["model"].strip()

    timeout_policy = resolved["runtime"]["timeout_policy"]
    assert timeout_policy["enabled"] is True
    assert timeout_policy["action"] == "stop_run"

    budget = resolved["budget"]
    assert budget["max_total_usd"] > 0
    assert budget["estimated_avg_cost_per_game_usd"] > 0


def test_transferability_role_overrides_template_has_required_roles() -> None:
    config_path = ROOT / "configs" / "ablations" / "transferability_moa_role_overrides_template.yaml"
    resolved, _ = resolve_with_hash(config_path)
    multi_agent = resolved["strategy"]["multi_agent"]

    assert multi_agent["enabled"] is True
    assert multi_agent["provider_policy"] == "role_model_overrides"

    role_models = multi_agent["role_models"]
    for role in ("tactical", "positional", "endgame", "aggregator"):
        assert role in role_models
        assert isinstance(role_models[role], str)
        assert role_models[role].strip()
