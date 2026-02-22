from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass
class EloEstimate:
    estimate: float
    ci_95: tuple[float, float]
    std_error: float
    n_games: int


def logistic_expected(opponent_elo: float, player_elo: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent_elo - player_elo) / 400.0))


def estimate_elo_mle(
    observations: Iterable[tuple[float, float]],
    color_correction_elo: float = 0.0,
) -> EloEstimate:
    """Estimate player Elo with MLE from (opponent_elo, score) observations."""
    obs = list(observations)
    if not obs:
        raise ValueError("At least one observation is required for Elo estimation")

    opp_elos = [float(opp) for opp, _ in obs]
    scores = [float(score) for _, score in obs]

    def score_diff(player_elo: float) -> float:
        return sum(score - logistic_expected(opp, player_elo) for opp, score in zip(opp_elos, scores))

    lo = min(opp_elos) - 2000.0
    hi = max(opp_elos) + 2000.0

    f_lo = score_diff(lo)
    f_hi = score_diff(hi)
    if f_lo < 0:
        root = lo
    elif f_hi > 0:
        root = hi
    else:
        for _ in range(80):
            mid = (lo + hi) / 2.0
            f_mid = score_diff(mid)
            if abs(f_mid) < 1e-10:
                root = mid
                break
            if f_mid > 0:
                lo = mid
            else:
                hi = mid
        else:
            root = (lo + hi) / 2.0

    ln10_over_400 = math.log(10.0) / 400.0
    fisher = 0.0
    for opp in opp_elos:
        p = logistic_expected(opp, root)
        fisher += p * (1.0 - p) * (ln10_over_400**2)
    std_error = float("inf") if fisher <= 0 else 1.0 / math.sqrt(fisher)

    corrected = root + color_correction_elo
    if math.isfinite(std_error):
        ci = (corrected - 1.96 * std_error, corrected + 1.96 * std_error)
    else:
        ci = (float("-inf"), float("inf"))

    return EloEstimate(
        estimate=corrected,
        ci_95=ci,
        std_error=std_error,
        n_games=len(obs),
    )
