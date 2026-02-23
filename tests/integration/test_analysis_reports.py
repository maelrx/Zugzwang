from __future__ import annotations

import json
from pathlib import Path

import yaml

from zugzwang.analysis.reports import compare_runs, generate_markdown_report


def test_compare_runs_and_generate_markdown(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_a_id = "run_a-20260223T100000Z-aaaaaaaa"
    run_b_id = "run_b-20260223T100000Z-bbbbbbbb"

    _write_run(
        runs_root=runs_root,
        run_id=run_a_id,
        game_results=["0-1"] * 24,
        acpl_values=[22.0 + (idx % 3) for idx in range(24)],
    )
    _write_run(
        runs_root=runs_root,
        run_id=run_b_id,
        game_results=["1-0"] * 24,
        acpl_values=[88.0 + (idx % 4) for idx in range(24)],
    )

    report = compare_runs(
        run_a=run_a_id,
        run_b=run_b_id,
        runs_root=runs_root,
        iterations=2_000,
        permutations=2_000,
        confidence=0.95,
        alpha=0.05,
        seed=19,
    )

    assert report.win_rate_test.significant is True
    assert report.win_rate_test.delta > 0
    assert report.acpl_test is not None
    assert report.acpl_test.significant is True
    assert report.acpl_test.delta < 0
    assert "Run A" in report.recommendation

    markdown = generate_markdown_report(report)
    assert "# Run Comparison Report" in markdown
    assert run_a_id in markdown
    assert run_b_id in markdown
    assert "## Win Rate" in markdown
    assert "## ACPL" in markdown


def _write_run(
    *,
    runs_root: Path,
    run_id: str,
    game_results: list[str],
    acpl_values: list[float],
) -> None:
    run_dir = runs_root / run_id
    games_dir = run_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    resolved_config = {
        "experiment": {"name": "synthetic_compare", "target_valid_games": len(game_results)},
        "budget": {"max_total_usd": 5.0},
        "players": {
            "white": {"type": "random", "name": "random_white"},
            "black": {"type": "llm", "name": "llm_black", "provider": "mock", "model": "mock-1"},
        },
        "evaluation": {
            "auto": {"player_color": "auto"},
            "stockfish": {"depth": 8, "threads": 1, "hash_mb": 64, "path": None},
        },
    }
    (run_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(resolved_config, sort_keys=True),
        encoding="utf-8",
    )

    base_report = {
        "schema_version": "1.0",
        "experiment_id": run_id,
        "config_hash": "hash",
        "num_games_target": len(game_results),
        "num_games_scheduled": len(game_results),
        "num_games_valid": len(game_results),
        "completion_rate": 1.0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "win_loss_score": 0.5,
        "acpl_overall": sum(acpl_values) / len(acpl_values),
        "total_cost_usd": 0.0,
    }
    (run_dir / "experiment_report.json").write_text(json.dumps(base_report), encoding="utf-8")

    evaluated_report = dict(base_report)
    evaluated_report.update(
        {
            "schema_version": "2.0",
            "acpl_by_game": acpl_values,
            "evaluation": {"player_color": "black"},
        }
    )
    (run_dir / "experiment_report_evaluated.json").write_text(
        json.dumps(evaluated_report),
        encoding="utf-8",
    )

    for index, result in enumerate(game_results, start=1):
        game_payload = {
            "experiment_id": run_id,
            "game_number": index,
            "config_hash": "hash",
            "seed": index,
            "players": resolved_config["players"],
            "moves": [
                {
                    "ply_number": 1,
                    "color": "white",
                    "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    "move_decision": {
                        "move_uci": "e2e4",
                        "move_san": "e4",
                        "raw_response": "e2e4",
                        "parse_ok": True,
                        "is_legal": True,
                        "retry_count": 0,
                        "tokens_input": 0,
                        "tokens_output": 0,
                        "latency_ms": 0,
                        "provider_model": "random",
                    },
                },
                {
                    "ply_number": 2,
                    "color": "black",
                    "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    "move_decision": {
                        "move_uci": "e7e5",
                        "move_san": "e5",
                        "raw_response": "e7e5",
                        "parse_ok": True,
                        "is_legal": True,
                        "retry_count": 0,
                        "tokens_input": 10,
                        "tokens_output": 2,
                        "latency_ms": 5,
                        "provider_model": "mock-1",
                    },
                },
            ],
            "result": result,
            "termination": "checkmate",
            "token_usage": {"input": 10, "output": 2},
            "cost_usd": 0.0,
            "duration_seconds": 1.0,
            "timestamp_utc": "2026-02-23T00:00:00Z",
        }
        (games_dir / f"game_{index:04d}.json").write_text(json.dumps(game_payload), encoding="utf-8")
