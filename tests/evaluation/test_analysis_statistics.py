from __future__ import annotations

from zugzwang.analysis.statistics import bootstrap_win_rate, compare_acpl, compare_win_rates


def test_bootstrap_win_rate_ci_contains_expected_center() -> None:
    samples = [1.0, 0.0] * 40
    result = bootstrap_win_rate(samples, iterations=2_000, confidence=0.95, seed=7)

    assert 0.45 <= result.mean <= 0.55
    assert result.ci_low <= 0.5 <= result.ci_high


def test_compare_win_rates_detects_extreme_difference() -> None:
    run_a = [1.0] * 30
    run_b = [0.0] * 30

    comparison = compare_win_rates(
        run_a,
        run_b,
        iterations=2_000,
        permutations=2_000,
        confidence=0.95,
        alpha=0.05,
        seed=11,
    )

    assert comparison.significant is True
    assert comparison.delta > 0.9
    assert comparison.p_value < 0.01
    assert comparison.effect_size_magnitude == "large"


def test_compare_win_rates_marks_neutral_case_as_non_significant() -> None:
    run_a = [1.0, 0.5, 0.0] * 20
    run_b = [1.0, 0.5, 0.0] * 20

    comparison = compare_win_rates(
        run_a,
        run_b,
        iterations=2_000,
        permutations=2_000,
        confidence=0.95,
        alpha=0.05,
        seed=13,
    )

    assert comparison.significant is False
    assert comparison.p_value >= 0.05
    assert abs(comparison.delta) <= 1e-12


def test_compare_acpl_detects_large_gap() -> None:
    run_a = [20.0 + (i % 3) for i in range(30)]
    run_b = [120.0 + (i % 5) for i in range(30)]

    comparison = compare_acpl(
        run_a,
        run_b,
        iterations=2_000,
        permutations=2_000,
        confidence=0.95,
        alpha=0.05,
        seed=17,
    )

    assert comparison.significant is True
    assert comparison.delta < 0
    assert comparison.p_value < 0.01
