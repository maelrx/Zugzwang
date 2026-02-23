from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from zugzwang.api import deps
from zugzwang.api.main import create_app
from zugzwang.api.services import ArtifactService


def test_analysis_compare_route_and_markdown_download(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_a_id = "route_a-20260223T110000Z-aaaaaaaa"
    run_b_id = "route_b-20260223T110000Z-bbbbbbbb"

    _write_run(
        runs_root=runs_root,
        run_id=run_a_id,
        game_results=["0-1"] * 20,
        acpl_values=[25.0 + (idx % 2) for idx in range(20)],
    )
    _write_run(
        runs_root=runs_root,
        run_id=run_b_id,
        game_results=["1-0"] * 20,
        acpl_values=[90.0 + (idx % 3) for idx in range(20)],
    )

    app = create_app()
    app.dependency_overrides[deps.get_artifact_service] = lambda: ArtifactService(root=runs_root)
    client = TestClient(app)

    response = client.post(
        "/api/analysis/compare",
        json={
            "run_a": run_a_id,
            "run_b": run_b_id,
            "bootstrap_iterations": 1_500,
            "permutation_iterations": 1_500,
            "seed": 23,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["metrics"]["win_rate"]["significant"] is True
    assert payload["metrics"]["acpl"]["significant"] is True
    assert payload["recommendation"].startswith("Run A")

    comparison_id = payload["comparison_id"]
    saved_json = Path(payload["artifacts"]["json_path"])
    saved_md = Path(payload["artifacts"]["markdown_path"])
    assert saved_json.exists()
    assert saved_md.exists()

    read_payload = client.get(f"/api/analysis/compare/{comparison_id}")
    assert read_payload.status_code == 200
    assert read_payload.json()["comparison_id"] == comparison_id

    markdown_response = client.get(f"/api/analysis/compare/{comparison_id}/report.md")
    assert markdown_response.status_code == 200
    assert "Run Comparison Report" in markdown_response.text


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
        "experiment": {"name": "api_compare", "target_valid_games": len(game_results)},
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

    report = {
        "schema_version": "2.0",
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
        "acpl_by_game": acpl_values,
        "evaluation": {"player_color": "black"},
        "total_cost_usd": 0.0,
    }
    (run_dir / "experiment_report.json").write_text(json.dumps(report), encoding="utf-8")
    (run_dir / "experiment_report_evaluated.json").write_text(json.dumps(report), encoding="utf-8")

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
