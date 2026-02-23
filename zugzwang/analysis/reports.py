from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import yaml

from zugzwang.analysis.plots import ascii_histogram, format_ci_line
from zugzwang.analysis.statistics import (
    BootstrapCI,
    ComparisonTest,
    bootstrap_acpl,
    bootstrap_win_rate,
    compare_acpl,
    compare_win_rates,
)
from zugzwang.evaluation.metrics import NON_VALID_TERMINATIONS
from zugzwang.evaluation.player_color import infer_evaluation_player_color
from zugzwang.experiments.io import load_game_records


@dataclass(frozen=True)
class RunSample:
    run_id: str
    run_dir: str
    player_color: str
    win_scores: list[float]
    acpl_values: list[float]
    total_games: int
    valid_games: int


@dataclass(frozen=True)
class RunComparisonReport:
    comparison_id: str
    created_at_utc: str
    run_a: RunSample
    run_b: RunSample
    win_rate_a: BootstrapCI
    win_rate_b: BootstrapCI
    win_rate_test: ComparisonTest
    acpl_a: BootstrapCI | None
    acpl_b: BootstrapCI | None
    acpl_test: ComparisonTest | None
    recommendation: str
    confidence_note: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "comparison_id": self.comparison_id,
            "created_at_utc": self.created_at_utc,
            "runs": {
                "a": _run_sample_to_dict(self.run_a),
                "b": _run_sample_to_dict(self.run_b),
            },
            "metrics": {
                "win_rate": _metric_to_dict(self.win_rate_a, self.win_rate_b, self.win_rate_test),
                "acpl": (
                    _metric_to_dict(self.acpl_a, self.acpl_b, self.acpl_test)
                    if self.acpl_a is not None and self.acpl_b is not None and self.acpl_test is not None
                    else None
                ),
            },
            "recommendation": self.recommendation,
            "confidence_note": self.confidence_note,
            "notes": list(self.notes),
        }
        return payload


def compare_runs(
    run_a: str | Path,
    run_b: str | Path,
    *,
    runs_root: str | Path = "results/runs",
    comparison_id: str | None = None,
    iterations: int = 10_000,
    permutations: int = 10_000,
    confidence: float = 0.95,
    alpha: float = 0.05,
    seed: int = 42,
) -> RunComparisonReport:
    root = Path(runs_root)
    sample_a = _load_run_sample(run_a, runs_root=root)
    sample_b = _load_run_sample(run_b, runs_root=root)

    win_rate_a = bootstrap_win_rate(
        sample_a.win_scores,
        iterations=iterations,
        confidence=confidence,
        seed=seed,
    )
    win_rate_b = bootstrap_win_rate(
        sample_b.win_scores,
        iterations=iterations,
        confidence=confidence,
        seed=seed,
    )
    win_rate_test = compare_win_rates(
        sample_a.win_scores,
        sample_b.win_scores,
        iterations=iterations,
        permutations=permutations,
        confidence=confidence,
        alpha=alpha,
        seed=seed,
    )

    acpl_a: BootstrapCI | None = None
    acpl_b: BootstrapCI | None = None
    acpl_test: ComparisonTest | None = None
    if sample_a.acpl_values and sample_b.acpl_values:
        acpl_a = bootstrap_acpl(
            sample_a.acpl_values,
            iterations=iterations,
            confidence=confidence,
            seed=seed,
        )
        acpl_b = bootstrap_acpl(
            sample_b.acpl_values,
            iterations=iterations,
            confidence=confidence,
            seed=seed,
        )
        acpl_test = compare_acpl(
            sample_a.acpl_values,
            sample_b.acpl_values,
            iterations=iterations,
            permutations=permutations,
            confidence=confidence,
            alpha=alpha,
            seed=seed,
        )

    notes: list[str] = []
    min_games = min(len(sample_a.win_scores), len(sample_b.win_scores))
    if min_games < 10:
        notes.append("Low game count per run (<10 valid games). Treat significance as preliminary.")
    if not sample_a.acpl_values or not sample_b.acpl_values:
        notes.append("ACPL comparison unavailable for one or both runs (missing evaluated report).")
    elif min(len(sample_a.acpl_values), len(sample_b.acpl_values)) == 1:
        notes.append("ACPL comparison uses aggregate-only samples (single value per run).")

    recommendation = _build_recommendation(win_rate_test=win_rate_test, acpl_test=acpl_test)
    confidence_note = _build_confidence_note(
        win_rate_test=win_rate_test,
        acpl_test=acpl_test,
        min_games=min_games,
    )

    created_at_utc = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    comparison_key = comparison_id or _default_comparison_id(sample_a.run_id, sample_b.run_id)
    return RunComparisonReport(
        comparison_id=comparison_key,
        created_at_utc=created_at_utc,
        run_a=sample_a,
        run_b=sample_b,
        win_rate_a=win_rate_a,
        win_rate_b=win_rate_b,
        win_rate_test=win_rate_test,
        acpl_a=acpl_a,
        acpl_b=acpl_b,
        acpl_test=acpl_test,
        recommendation=recommendation,
        confidence_note=confidence_note,
        notes=notes,
    )


def generate_markdown_report(report: RunComparisonReport) -> str:
    payload = report.to_dict()
    win = payload["metrics"]["win_rate"]
    acpl = payload["metrics"]["acpl"]

    lines: list[str] = [
        "# Run Comparison Report",
        "",
        f"- Comparison ID: `{report.comparison_id}`",
        f"- Generated at (UTC): `{report.created_at_utc}`",
        f"- Run A: `{report.run_a.run_id}`",
        f"- Run B: `{report.run_b.run_id}`",
        "",
        "## Summary",
        "",
        f"- Recommendation: {report.recommendation}",
        f"- Confidence: {report.confidence_note}",
    ]

    if report.notes:
        lines.append("- Notes:")
        for note in report.notes:
            lines.append(f"  - {note}")

    lines.extend(
        [
            "",
            "## Win Rate (higher is better)",
            "",
            format_ci_line("Run A", win["run_a"]["mean"], win["run_a"]["ci_low"], win["run_a"]["ci_high"]),
            format_ci_line("Run B", win["run_b"]["mean"], win["run_b"]["ci_low"], win["run_b"]["ci_high"]),
            (
                "- Delta (A-B): "
                f"{win['delta']:.4f}, 95% CI=[{win['ci_low']:.4f}, {win['ci_high']:.4f}], "
                f"p={win['p_value']:.4f}, effect={win['effect_size_name']} {win['effect_size']:.4f} "
                f"({win['effect_size_magnitude']})"
            ),
            "",
            "```text",
            ascii_histogram(report.run_a.win_scores, label=f"{report.run_a.run_id} win scores"),
            ascii_histogram(report.run_b.win_scores, label=f"{report.run_b.run_id} win scores"),
            "```",
        ]
    )

    lines.extend(["", "## ACPL (lower is better)", ""])
    if acpl is None:
        lines.append("ACPL data unavailable for at least one run.")
    else:
        lines.extend(
            [
                format_ci_line(
                    "Run A",
                    acpl["run_a"]["mean"],
                    acpl["run_a"]["ci_low"],
                    acpl["run_a"]["ci_high"],
                ),
                format_ci_line(
                    "Run B",
                    acpl["run_b"]["mean"],
                    acpl["run_b"]["ci_low"],
                    acpl["run_b"]["ci_high"],
                ),
                (
                    "- Delta (A-B): "
                    f"{acpl['delta']:.4f}, 95% CI=[{acpl['ci_low']:.4f}, {acpl['ci_high']:.4f}], "
                    f"p={acpl['p_value']:.4f}, effect={acpl['effect_size_name']} {acpl['effect_size']:.4f} "
                    f"({acpl['effect_size_magnitude']})"
                ),
                "",
                "```text",
                ascii_histogram(report.run_a.acpl_values, label=f"{report.run_a.run_id} ACPL"),
                ascii_histogram(report.run_b.acpl_values, label=f"{report.run_b.run_id} ACPL"),
                "```",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _load_run_sample(run_ref: str | Path, *, runs_root: Path) -> RunSample:
    run_dir = _resolve_run_dir(run_ref, runs_root=runs_root)
    run_id = run_dir.name
    player_color = _infer_player_color(run_dir)

    records = load_game_records(run_dir / "games")
    if not records:
        raise ValueError(f"No game records found in run: {run_id}")

    valid_records = [record for record in records if record.termination not in NON_VALID_TERMINATIONS]
    if not valid_records:
        raise ValueError(f"Run has no valid games for comparison: {run_id}")

    win_scores = [_result_score_for_player(record.result, player_color) for record in valid_records]
    acpl_values = _load_acpl_values(run_dir)
    return RunSample(
        run_id=run_id,
        run_dir=str(run_dir),
        player_color=player_color,
        win_scores=win_scores,
        acpl_values=acpl_values,
        total_games=len(records),
        valid_games=len(valid_records),
    )


def _resolve_run_dir(run_ref: str | Path, *, runs_root: Path) -> Path:
    candidate = Path(run_ref)
    if candidate.exists():
        return candidate.resolve()
    joined = runs_root / candidate
    if joined.exists():
        return joined.resolve()
    raise FileNotFoundError(f"Run directory not found: {run_ref}")


def _load_acpl_values(run_dir: Path) -> list[float]:
    evaluated_report = _load_json(run_dir / "experiment_report_evaluated.json")
    if not isinstance(evaluated_report, dict):
        return []

    by_game = evaluated_report.get("acpl_by_game")
    if isinstance(by_game, list):
        values = [_as_float(item) for item in by_game]
        numeric = [item for item in values if item is not None]
        if numeric:
            return numeric

    acpl_overall = _as_float(evaluated_report.get("acpl_overall"))
    if acpl_overall is None:
        return []
    return [acpl_overall]


def _infer_player_color(run_dir: Path) -> str:
    config = _load_yaml(run_dir / "resolved_config.yaml")
    if not isinstance(config, dict):
        return "black"

    requested = "auto"
    evaluation_cfg = config.get("evaluation")
    if isinstance(evaluation_cfg, dict):
        auto_cfg = evaluation_cfg.get("auto")
        if isinstance(auto_cfg, dict):
            raw = auto_cfg.get("player_color")
            if isinstance(raw, str) and raw.strip():
                requested = raw.strip()

    try:
        color, _ = infer_evaluation_player_color(config, requested)
    except ValueError:
        return "black"
    return color


def _result_score_for_player(result: str, player_color: str) -> float:
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if player_color == "white" else 0.0
    if result == "0-1":
        return 1.0 if player_color == "black" else 0.0
    return 0.5


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _load_yaml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    return raw


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _run_sample_to_dict(sample: RunSample) -> dict[str, Any]:
    return {
        "run_id": sample.run_id,
        "run_dir": sample.run_dir,
        "player_color": sample.player_color,
        "total_games": sample.total_games,
        "valid_games": sample.valid_games,
        "sample_size_win": len(sample.win_scores),
        "sample_size_acpl": len(sample.acpl_values),
    }


def _metric_to_dict(
    metric_a: BootstrapCI,
    metric_b: BootstrapCI,
    comparison: ComparisonTest,
) -> dict[str, Any]:
    return {
        "name": comparison.metric_name,
        "run_a": {
            "mean": metric_a.mean,
            "ci_low": metric_a.ci_low,
            "ci_high": metric_a.ci_high,
            "confidence": metric_a.confidence,
            "sample_size": metric_a.sample_size,
        },
        "run_b": {
            "mean": metric_b.mean,
            "ci_low": metric_b.ci_low,
            "ci_high": metric_b.ci_high,
            "confidence": metric_b.confidence,
            "sample_size": metric_b.sample_size,
        },
        "delta": comparison.delta,
        "ci_low": comparison.ci_low,
        "ci_high": comparison.ci_high,
        "p_value": comparison.p_value,
        "effect_size": comparison.effect_size,
        "effect_size_name": comparison.effect_size_name,
        "effect_size_magnitude": comparison.effect_size_magnitude,
        "significant": comparison.significant,
    }


def _build_recommendation(
    *,
    win_rate_test: ComparisonTest,
    acpl_test: ComparisonTest | None,
) -> str:
    win_winner = _winner_from_delta(win_rate_test.delta, prefer_lower=False) if win_rate_test.significant else None
    acpl_winner = (
        _winner_from_delta(acpl_test.delta, prefer_lower=True)
        if acpl_test is not None and acpl_test.significant
        else None
    )

    if win_winner and acpl_winner and win_winner == acpl_winner:
        return f"Run {win_winner} is preferred: significant gains in win rate and ACPL."
    if win_winner and acpl_winner and win_winner != acpl_winner:
        return "No clear winner: win-rate and ACPL significance disagree between runs."
    if win_winner:
        return f"Run {win_winner} is preferred by significant win-rate improvement."
    if acpl_winner:
        return f"Run {acpl_winner} is preferred by significant ACPL improvement."
    return "No statistically significant winner at current alpha/confidence settings."


def _build_confidence_note(
    *,
    win_rate_test: ComparisonTest,
    acpl_test: ComparisonTest | None,
    min_games: int,
) -> str:
    any_significant = win_rate_test.significant or bool(acpl_test and acpl_test.significant)
    if min_games < 10:
        return "Low confidence: very small sample size."
    if min_games < 30:
        if any_significant:
            return "Moderate confidence: significant result observed with small-to-medium sample."
        return "Moderate confidence: no significance detected yet with current sample size."
    if any_significant:
        return "High confidence: at least one metric reached significance with >=30 games per run."
    return "Moderate confidence: no significant difference detected."


def _winner_from_delta(delta: float, *, prefer_lower: bool) -> str:
    if prefer_lower:
        return "A" if delta < 0 else "B"
    return "A" if delta > 0 else "B"


def _default_comparison_id(run_a_id: str, run_b_id: str) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"compare-{run_a_id}-vs-{run_b_id}-{stamp}"
