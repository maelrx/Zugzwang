from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Sequence


_EPSILON = 1e-12


@dataclass(frozen=True)
class BootstrapCI:
    metric_name: str
    mean: float
    ci_low: float
    ci_high: float
    confidence: float
    sample_size: int
    iterations: int
    seed: int


@dataclass(frozen=True)
class ComparisonTest:
    metric_name: str
    mean_a: float
    mean_b: float
    delta: float
    ci_low: float
    ci_high: float
    p_value: float
    effect_size: float
    effect_size_name: str
    effect_size_magnitude: str
    significant: bool
    confidence: float
    sample_size_a: int
    sample_size_b: int
    iterations: int
    permutations: int
    seed: int


def bootstrap_win_rate(
    outcomes: Sequence[float],
    *,
    iterations: int = 10_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    values = _validate_samples(outcomes, name="outcomes")
    for value in values:
        if value < 0.0 or value > 1.0:
            raise ValueError("outcomes values must be in [0.0, 1.0]")
    mean, ci_low, ci_high = _bootstrap_mean_ci(values, iterations=iterations, confidence=confidence, seed=seed)
    return BootstrapCI(
        metric_name="win_rate",
        mean=mean,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence=confidence,
        sample_size=len(values),
        iterations=iterations,
        seed=seed,
    )


def bootstrap_acpl(
    acpl_values: Sequence[float],
    *,
    iterations: int = 10_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    values = _validate_samples(acpl_values, name="acpl_values")
    mean, ci_low, ci_high = _bootstrap_mean_ci(values, iterations=iterations, confidence=confidence, seed=seed)
    return BootstrapCI(
        metric_name="acpl",
        mean=mean,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence=confidence,
        sample_size=len(values),
        iterations=iterations,
        seed=seed,
    )


def compare_win_rates(
    outcomes_a: Sequence[float],
    outcomes_b: Sequence[float],
    *,
    iterations: int = 10_000,
    permutations: int = 10_000,
    confidence: float = 0.95,
    alpha: float = 0.05,
    seed: int = 42,
) -> ComparisonTest:
    values_a = _validate_samples(outcomes_a, name="outcomes_a")
    values_b = _validate_samples(outcomes_b, name="outcomes_b")
    for value in values_a + values_b:
        if value < 0.0 or value > 1.0:
            raise ValueError("win-rate samples must be in [0.0, 1.0]")

    mean_a = _mean(values_a)
    mean_b = _mean(values_b)
    delta = mean_a - mean_b
    ci_low, ci_high = _bootstrap_delta_ci(
        values_a,
        values_b,
        iterations=iterations,
        confidence=confidence,
        seed=seed,
    )
    p_value = _permutation_p_value(
        values_a,
        values_b,
        permutations=permutations,
        seed=seed,
    )
    effect_size = _cohen_h(mean_a, mean_b)
    effect_size_magnitude = _cohen_h_magnitude(effect_size)
    return ComparisonTest(
        metric_name="win_rate",
        mean_a=mean_a,
        mean_b=mean_b,
        delta=delta,
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=p_value,
        effect_size=effect_size,
        effect_size_name="cohen_h",
        effect_size_magnitude=effect_size_magnitude,
        significant=bool(p_value < alpha),
        confidence=confidence,
        sample_size_a=len(values_a),
        sample_size_b=len(values_b),
        iterations=iterations,
        permutations=permutations,
        seed=seed,
    )


def compare_acpl(
    acpl_a: Sequence[float],
    acpl_b: Sequence[float],
    *,
    iterations: int = 10_000,
    permutations: int = 10_000,
    confidence: float = 0.95,
    alpha: float = 0.05,
    seed: int = 42,
) -> ComparisonTest:
    values_a = _validate_samples(acpl_a, name="acpl_a")
    values_b = _validate_samples(acpl_b, name="acpl_b")

    mean_a = _mean(values_a)
    mean_b = _mean(values_b)
    delta = mean_a - mean_b
    ci_low, ci_high = _bootstrap_delta_ci(
        values_a,
        values_b,
        iterations=iterations,
        confidence=confidence,
        seed=seed,
    )
    p_value = _permutation_p_value(
        values_a,
        values_b,
        permutations=permutations,
        seed=seed,
    )
    effect_size = _cliffs_delta(values_a, values_b)
    effect_size_magnitude = _cliffs_delta_magnitude(effect_size)
    return ComparisonTest(
        metric_name="acpl",
        mean_a=mean_a,
        mean_b=mean_b,
        delta=delta,
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=p_value,
        effect_size=effect_size,
        effect_size_name="cliffs_delta",
        effect_size_magnitude=effect_size_magnitude,
        significant=bool(p_value < alpha),
        confidence=confidence,
        sample_size_a=len(values_a),
        sample_size_b=len(values_b),
        iterations=iterations,
        permutations=permutations,
        seed=seed,
    )


def _validate_samples(values: Sequence[float], *, name: str) -> list[float]:
    if not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence of numeric values")
    output: list[float] = []
    for value in values:
        if not isinstance(value, int | float):
            raise TypeError(f"{name} must contain only int/float values")
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{name} contains non-finite value")
        output.append(parsed)
    if not output:
        raise ValueError(f"{name} must not be empty")
    return output


def _bootstrap_mean_ci(
    values: Sequence[float],
    *,
    iterations: int,
    confidence: float,
    seed: int,
) -> tuple[float, float, float]:
    _validate_common_params(iterations=iterations, confidence=confidence)
    sample = list(values)
    mean = _mean(sample)
    if len(sample) == 1:
        return mean, mean, mean

    rng = random.Random(seed)
    sample_size = len(sample)
    means: list[float] = []
    for _ in range(iterations):
        draw = [sample[rng.randrange(sample_size)] for _ in range(sample_size)]
        means.append(_mean(draw))
    means.sort()
    lower_q = (1.0 - confidence) / 2.0
    upper_q = 1.0 - lower_q
    return mean, _percentile(means, lower_q), _percentile(means, upper_q)


def _bootstrap_delta_ci(
    values_a: Sequence[float],
    values_b: Sequence[float],
    *,
    iterations: int,
    confidence: float,
    seed: int,
) -> tuple[float, float]:
    _validate_common_params(iterations=iterations, confidence=confidence)
    sample_a = list(values_a)
    sample_b = list(values_b)
    if len(sample_a) == 1 and len(sample_b) == 1:
        delta = sample_a[0] - sample_b[0]
        return delta, delta

    rng = random.Random(seed)
    n_a = len(sample_a)
    n_b = len(sample_b)
    deltas: list[float] = []
    for _ in range(iterations):
        draw_a = [sample_a[rng.randrange(n_a)] for _ in range(n_a)]
        draw_b = [sample_b[rng.randrange(n_b)] for _ in range(n_b)]
        deltas.append(_mean(draw_a) - _mean(draw_b))
    deltas.sort()
    lower_q = (1.0 - confidence) / 2.0
    upper_q = 1.0 - lower_q
    return _percentile(deltas, lower_q), _percentile(deltas, upper_q)


def _permutation_p_value(
    values_a: Sequence[float],
    values_b: Sequence[float],
    *,
    permutations: int,
    seed: int,
) -> float:
    if permutations <= 0:
        raise ValueError("permutations must be > 0")
    sample_a = list(values_a)
    sample_b = list(values_b)
    observed = _mean(sample_a) - _mean(sample_b)
    if abs(observed) <= _EPSILON:
        return 1.0

    combined = sample_a + sample_b
    if all(abs(value - combined[0]) <= _EPSILON for value in combined):
        return 1.0

    n_a = len(sample_a)
    rng = random.Random(seed)
    extreme = 0
    pool = list(combined)
    observed_abs = abs(observed)
    for _ in range(permutations):
        rng.shuffle(pool)
        perm_delta = _mean(pool[:n_a]) - _mean(pool[n_a:])
        if abs(perm_delta) >= observed_abs - _EPSILON:
            extreme += 1
    return (extreme + 1) / (permutations + 1)


def _validate_common_params(*, iterations: int, confidence: float) -> None:
    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence must be in (0.0, 1.0)")


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values))


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute percentile of empty values")
    if percentile <= 0.0:
        return float(sorted_values[0])
    if percentile >= 1.0:
        return float(sorted_values[-1])

    index = percentile * (len(sorted_values) - 1)
    lower_idx = int(math.floor(index))
    upper_idx = int(math.ceil(index))
    if lower_idx == upper_idx:
        return float(sorted_values[lower_idx])
    lower = float(sorted_values[lower_idx])
    upper = float(sorted_values[upper_idx])
    weight = index - lower_idx
    return lower + (upper - lower) * weight


def _cohen_h(p_a: float, p_b: float) -> float:
    clamped_a = min(1.0, max(0.0, p_a))
    clamped_b = min(1.0, max(0.0, p_b))
    return 2.0 * math.asin(math.sqrt(clamped_a)) - 2.0 * math.asin(math.sqrt(clamped_b))


def _cohen_h_magnitude(value: float) -> str:
    magnitude = abs(value)
    if magnitude < 0.2:
        return "negligible"
    if magnitude < 0.5:
        return "small"
    if magnitude < 0.8:
        return "medium"
    return "large"


def _cliffs_delta(values_a: Sequence[float], values_b: Sequence[float]) -> float:
    greater = 0
    lower = 0
    for value_a in values_a:
        for value_b in values_b:
            if value_a > value_b:
                greater += 1
            elif value_a < value_b:
                lower += 1
    total = len(values_a) * len(values_b)
    if total <= 0:
        return 0.0
    return float((greater - lower) / total)


def _cliffs_delta_magnitude(value: float) -> str:
    magnitude = abs(value)
    if magnitude < 0.147:
        return "negligible"
    if magnitude < 0.33:
        return "small"
    if magnitude < 0.474:
        return "medium"
    return "large"
