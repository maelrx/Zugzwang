from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunIndexEntry:
    run_id: str
    created_at_utc: str
    config_hash: str
    template_path: str
    provider: str
    model: str
    games_valid: int | None
    games_target: int | None
    completion_rate: float | None
    acpl_overall: float | None
    elo_estimate: float | None
    total_cost_usd: float | None
    evaluated_report_exists: bool


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_path(value: str | None) -> str:
    if not value:
        return "--"
    return value.replace("\\", "/")


def _short_hash(value: str) -> str:
    if value in {"", "--"}:
        return "--"
    if len(value) <= 12:
        return value
    return f"{value[:8]}..."


def _format_float(value: float | None, decimals: int) -> str:
    if value is None:
        return "--"
    return f"{value:.{decimals}f}"


def _parse_timestamp(value: str) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _extract_entry(run_dir: Path) -> RunIndexEntry:
    run_meta = _load_json(run_dir / "_run.json")
    report = _load_json(run_dir / "experiment_report.json")
    evaluated_report = _load_json(run_dir / "experiment_report_evaluated.json")

    run_id = str(run_meta.get("run_id") or report.get("experiment_id") or run_dir.name)
    created_at_utc = str(run_meta.get("created_at_utc") or "--")
    config_hash = str(run_meta.get("config_hash") or report.get("config_hash") or "--")

    paths = run_meta.get("paths")
    config_path = "--"
    if isinstance(paths, dict):
        config_path = _normalize_path(paths.get("config_path"))

    resolved_config = run_meta.get("resolved_config")
    provider = "--"
    model = "--"
    if isinstance(resolved_config, dict):
        players = resolved_config.get("players")
        if isinstance(players, dict):
            black = players.get("black")
            if isinstance(black, dict):
                provider = str(black.get("provider") or "--")
                model = str(black.get("model") or "--")

    elo_estimate = _as_float(evaluated_report.get("elo_estimate")) or _as_float(report.get("elo_estimate"))
    acpl_overall = _as_float(evaluated_report.get("acpl_overall")) or _as_float(report.get("acpl_overall"))

    return RunIndexEntry(
        run_id=run_id,
        created_at_utc=created_at_utc,
        config_hash=config_hash,
        template_path=config_path,
        provider=provider,
        model=model,
        games_valid=_as_int(report.get("num_games_valid")),
        games_target=_as_int(report.get("num_games_target")),
        completion_rate=_as_float(report.get("completion_rate")),
        acpl_overall=acpl_overall,
        elo_estimate=elo_estimate,
        total_cost_usd=_as_float(report.get("total_cost_usd")),
        evaluated_report_exists=(run_dir / "experiment_report_evaluated.json").exists(),
    )


def build_index(runs_root: Path, limit: int) -> list[RunIndexEntry]:
    if not runs_root.exists():
        return []

    entries: list[RunIndexEntry] = []
    for run_dir in runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        if run_dir.name.startswith("_"):
            continue
        entries.append(_extract_entry(run_dir))

    entries.sort(key=lambda item: _parse_timestamp(item.created_at_utc), reverse=True)
    return entries[:limit]


def build_markdown(entries: list[RunIndexEntry], runs_root: Path) -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    evaluated_count = sum(1 for item in entries if item.evaluated_report_exists)

    lines: list[str] = []
    lines.append("# Results Index")
    lines.append("")
    lines.append(f"Generated at: `{generated_at}`")
    lines.append(f"Runs root: `{runs_root.as_posix()}`")
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    lines.append(f"- Total indexed runs: **{len(entries)}**")
    lines.append(f"- Runs with evaluated report: **{evaluated_count}**")
    lines.append("")
    lines.append("## Latest Runs")
    lines.append("")
    lines.append("| Run ID | Created UTC | Provider/Model | Template | Config Hash | Games | Completion | ACPL | Elo | Cost USD |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|---:|")

    if not entries:
        lines.append("| -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |")
    else:
        for entry in entries:
            provider_model = f"{entry.provider}/{entry.model}"
            template = Path(entry.template_path).name if entry.template_path not in {"", "--"} else "--"
            games_text = "--"
            if entry.games_valid is not None and entry.games_target is not None:
                games_text = f"{entry.games_valid}/{entry.games_target}"
            lines.append(
                "| "
                + " | ".join(
                    [
                        entry.run_id,
                        entry.created_at_utc,
                        provider_model,
                        template,
                        _short_hash(entry.config_hash),
                        games_text,
                        _format_float(entry.completion_rate, 3),
                        _format_float(entry.acpl_overall, 1),
                        _format_float(entry.elo_estimate, 1),
                        _format_float(entry.total_cost_usd, 4),
                    ]
                )
                + " |"
            )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Source files per run: `_run.json`, `experiment_report.json`, `experiment_report_evaluated.json`.")
    lines.append("- Values shown as `--` indicate missing artifacts or fields.")
    lines.append("- This file is generated. Re-run script after new experiments.")
    lines.append("")
    lines.append("```bash")
    lines.append("python tools/generate_results_index.py")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate markdown index for run artifacts.")
    parser.add_argument(
        "--runs-root",
        default="results/runs",
        help="Path to run artifacts root (default: results/runs).",
    )
    parser.add_argument(
        "--output",
        default="../techdocs/RESULTS_INDEX.md",
        help="Output markdown path (default: ../techdocs/RESULTS_INDEX.md).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of latest runs to include (default: 200).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    runs_root = (project_root / args.runs_root).resolve()
    output_path = (project_root / args.output).resolve()

    entries = build_index(runs_root=runs_root, limit=max(1, args.limit))
    markdown = build_markdown(entries=entries, runs_root=runs_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
