from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import chess
import yaml

from zugzwang.core.models import ExperimentReport, GameRecord
from zugzwang.evaluation.elo import estimate_elo_mle
from zugzwang.evaluation.metrics import summarize_experiment
from zugzwang.evaluation.move_quality import classify_centipawn_loss
from zugzwang.evaluation.stockfish import StockfishEvaluator
from zugzwang.experiments.io import load_game_records


def evaluate_run_dir(
    run_dir: str | Path,
    player_color: str = "black",
    opponent_elo: float | None = None,
    elo_color_correction: float = 0.0,
    output_filename: str = "experiment_report_evaluated.json",
) -> dict[str, Any]:
    run_path = Path(run_dir)
    if not run_path.exists():
        raise FileNotFoundError(f"Run directory not found: {run_path}")

    resolved_config = _load_resolved_config(run_path)
    config_hash = _load_config_hash(run_path)
    games_dir = run_path / "games"
    records = load_game_records(games_dir)
    if not records:
        raise ValueError(f"No game records found in {games_dir}")

    existing_report = _load_existing_report(run_path / "experiment_report.json")
    scheduled_games = (
        int(existing_report.get("num_games_scheduled", 0))
        if existing_report
        else len(records)
    )
    if scheduled_games <= 0:
        scheduled_games = len(records)

    budget_cap = float(resolved_config["budget"]["max_total_usd"])
    base_report = summarize_experiment(
        experiment_id=records[0].experiment_id,
        config_hash=config_hash,
        target_games=int(resolved_config["experiment"]["target_valid_games"]),
        scheduled_games=scheduled_games,
        game_records=records,
        budget_cap_usd=budget_cap,
        stopped_due_to_budget=bool(existing_report.get("stopped_due_to_budget", False))
        if existing_report
        else False,
        budget_stop_reason=existing_report.get("budget_stop_reason") if existing_report else None,
    )

    stockfish_cfg = resolved_config.get("evaluation", {}).get("stockfish", {})
    evaluator = StockfishEvaluator(
        depth=int(stockfish_cfg.get("depth", 12)),
        path=stockfish_cfg.get("path"),
        threads=int(stockfish_cfg.get("threads", 1)),
        hash_mb=int(stockfish_cfg.get("hash_mb", 128)),
    )
    with evaluator:
        move_quality = _evaluate_move_quality(
            records=records,
            evaluator=evaluator,
            player_color=player_color,
        )

    elo_estimate = None
    elo_ci = None
    if opponent_elo is not None:
        observations = [
            (opponent_elo, _result_score(record.result, player_color)) for record in records
        ]
        elo = estimate_elo_mle(observations, color_correction_elo=elo_color_correction)
        elo_estimate = float(elo.estimate)
        elo_ci = [float(elo.ci_95[0]), float(elo.ci_95[1])]

    enriched_report: ExperimentReport = replace(
        base_report,
        schema_version="2.0",
        elo_estimate=elo_estimate,
        elo_ci_95=elo_ci,
        acpl_overall=move_quality["acpl_overall"],
        acpl_by_phase=move_quality["acpl_by_phase"],
        blunder_rate=move_quality["blunder_rate"],
        best_move_agreement=move_quality["best_move_agreement"],
    )

    output = enriched_report.to_dict()
    output["evaluation"] = {
        "provider": "stockfish",
        "stockfish": {
            "path": evaluator.path,
            "depth": evaluator.depth,
            "threads": evaluator.threads,
            "hash_mb": evaluator.hash_mb,
        },
        "player_color": player_color,
        "opponent_elo": opponent_elo,
        "elo_color_correction": elo_color_correction,
        "evaluated_move_count": move_quality["evaluated_move_count"],
    }

    output_path = run_path / output_filename
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return {
        "run_dir": str(run_path),
        "input_games": len(records),
        "output_report": str(output_path),
        "evaluated_move_count": move_quality["evaluated_move_count"],
        "acpl_overall": move_quality["acpl_overall"],
        "blunder_rate": move_quality["blunder_rate"],
        "best_move_agreement": move_quality["best_move_agreement"],
        "elo_estimate": elo_estimate,
        "elo_ci_95": elo_ci,
    }


def _evaluate_move_quality(
    records: list[GameRecord],
    evaluator: StockfishEvaluator,
    player_color: str,
) -> dict[str, Any]:
    color_key = player_color.lower()
    if color_key not in {"white", "black"}:
        raise ValueError("player_color must be 'white' or 'black'")

    total_cp_loss = 0
    total_moves = 0
    blunders = 0
    best_count = 0
    by_phase_sum: dict[str, int] = {"opening": 0, "middlegame": 0, "endgame": 0}
    by_phase_count: dict[str, int] = {"opening": 0, "middlegame": 0, "endgame": 0}

    for record in records:
        for move in record.moves:
            if move.color.lower() != color_key:
                continue
            phase = _phase_from_fen(move.fen_before)
            try:
                evaluation = evaluator.evaluate_move(move.fen_before, move.move_decision.move_uci)
            except Exception:
                # Skip move if evaluation fails (e.g. malformed historical artifact).
                continue
            cp_loss = int(evaluation.centipawn_loss)
            classification = classify_centipawn_loss(cp_loss)

            total_cp_loss += cp_loss
            total_moves += 1
            by_phase_sum[phase] += cp_loss
            by_phase_count[phase] += 1

            if classification == "blunder":
                blunders += 1
            if move.move_decision.move_uci == evaluation.best_move_uci:
                best_count += 1

    acpl_by_phase: dict[str, float] = {}
    for phase in ("opening", "middlegame", "endgame"):
        count = by_phase_count[phase]
        acpl_by_phase[phase] = (by_phase_sum[phase] / count) if count else 0.0

    acpl_overall = (total_cp_loss / total_moves) if total_moves else 0.0
    blunder_rate = (blunders / total_moves) if total_moves else 0.0
    best_move_agreement = (best_count / total_moves) if total_moves else 0.0
    return {
        "acpl_overall": float(acpl_overall),
        "acpl_by_phase": acpl_by_phase,
        "blunder_rate": float(blunder_rate),
        "best_move_agreement": float(best_move_agreement),
        "evaluated_move_count": total_moves,
    }


def _phase_from_fen(fen: str) -> str:
    board = chess.Board(fen)
    piece_count = len(board.piece_map())
    if piece_count <= 10:
        return "endgame"
    if board.fullmove_number <= 12:
        return "opening"
    return "middlegame"


def _result_score(result: str, player_color: str) -> float:
    color = player_color.lower()
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if color == "white" else 0.0
    if result == "0-1":
        return 1.0 if color == "black" else 0.0
    return 0.5


def _load_resolved_config(run_path: Path) -> dict[str, Any]:
    config_path = run_path / "resolved_config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"resolved_config.yaml not found in {run_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid resolved_config.yaml in {run_path}")
    return raw


def _load_config_hash(run_path: Path) -> str:
    hash_path = run_path / "config_hash.txt"
    if not hash_path.exists():
        return "unknown"
    return hash_path.read_text(encoding="utf-8").strip()


def _load_existing_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    return raw
