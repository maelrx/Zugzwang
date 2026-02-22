from __future__ import annotations

from zugzwang.providers.pricing import estimate_zai_cost_usd


def test_estimate_zai_cost_glm5_standard_without_cache() -> None:
    cost = estimate_zai_cost_usd(
        model="glm-5",
        prompt_tokens=1000,
        completion_tokens=500,
        cached_prompt_tokens=0,
        mode="standard",
    )
    assert abs(cost - 0.0026) < 1e-9


def test_estimate_zai_cost_glm5_standard_with_cache() -> None:
    cost = estimate_zai_cost_usd(
        model="glm-5",
        prompt_tokens=1000,
        completion_tokens=0,
        cached_prompt_tokens=400,
        mode="standard",
    )
    assert abs(cost - 0.00068) < 1e-9


def test_estimate_zai_cost_coding_plan_mode_is_zero() -> None:
    cost = estimate_zai_cost_usd(
        model="glm-5",
        prompt_tokens=20_000,
        completion_tokens=40_000,
        cached_prompt_tokens=0,
        mode="coding_plan",
    )
    assert cost == 0.0
