from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("filename", "enabled", "mode", "proposer_count"),
    [
        ("moa_single_agent_control.yaml", False, "capability_moa", 2),
        ("moa_capability.yaml", True, "capability_moa", 2),
        ("moa_specialist.yaml", True, "specialist_moa", 3),
        ("moa_hybrid_phase.yaml", True, "hybrid_phase_router", 3),
    ],
)
def test_moa_ablation_configs_resolve_with_expected_guardrails(
    filename: str,
    enabled: bool,
    mode: str,
    proposer_count: int,
) -> None:
    config_path = ROOT / "configs" / "ablations" / filename
    resolved, cfg_hash = resolve_with_hash(config_path)

    assert len(cfg_hash) == 64
    assert resolved["protocol"]["mode"] == "research_strict"
    assert resolved["evaluation"]["auto"]["enabled"] is True

    timeout_policy = resolved["runtime"]["timeout_policy"]
    assert timeout_policy["enabled"] is True
    assert timeout_policy["action"] == "stop_run"

    budget = resolved["budget"]
    assert budget["max_total_usd"] > 0
    assert budget["estimated_avg_cost_per_game_usd"] > 0

    multi_agent = resolved["strategy"]["multi_agent"]
    assert multi_agent["enabled"] is enabled
    assert multi_agent["mode"] == mode
    assert multi_agent["proposer_count"] == proposer_count


def test_moa_cost_profiles_are_above_single_agent_control() -> None:
    single_path = ROOT / "configs" / "ablations" / "moa_single_agent_control.yaml"
    single_cfg, _ = resolve_with_hash(single_path)
    single_estimated = single_cfg["budget"]["estimated_avg_cost_per_game_usd"]
    single_cap = single_cfg["budget"]["max_total_usd"]

    for filename in ("moa_capability.yaml", "moa_specialist.yaml", "moa_hybrid_phase.yaml"):
        config_path = ROOT / "configs" / "ablations" / filename
        resolved, _ = resolve_with_hash(config_path)
        budget = resolved["budget"]
        assert budget["estimated_avg_cost_per_game_usd"] > single_estimated
        assert budget["max_total_usd"] > single_cap
