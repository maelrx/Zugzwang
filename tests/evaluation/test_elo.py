from __future__ import annotations

from zugzwang.evaluation.elo import estimate_elo_mle


def test_elo_mle_equal_score_matches_opponent() -> None:
    observations = [(1200.0, 0.5) for _ in range(40)]
    estimate = estimate_elo_mle(observations)
    assert abs(estimate.estimate - 1200.0) < 1.0
    assert estimate.n_games == 40


def test_elo_mle_higher_score_increases_estimate() -> None:
    observations = [(1000.0, 1.0) for _ in range(20)] + [(1000.0, 0.5) for _ in range(10)]
    estimate = estimate_elo_mle(observations)
    assert estimate.estimate > 1000.0
    assert estimate.ci_95[1] > estimate.ci_95[0]
