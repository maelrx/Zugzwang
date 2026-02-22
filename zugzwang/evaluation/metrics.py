from __future__ import annotations

import math
from typing import Iterable

from zugzwang.core.models import ExperimentReport, GameRecord

NON_VALID_TERMINATIONS = {"error", "timeout", "provider_failure"}


def summarize_experiment(
    experiment_id: str,
    config_hash: str,
    target_games: int,
    scheduled_games: int,
    game_records: Iterable[GameRecord],
    budget_cap_usd: float | None = None,
    stopped_due_to_budget: bool = False,
    budget_stop_reason: str | None = None,
    stopped_due_to_reliability: bool = False,
    reliability_stop_reason: str | None = None,
) -> ExperimentReport:
    records = list(game_records)
    total_records = len(records)
    valid_games = 0
    nonvalid_games = 0

    wins = sum(1 for rec in records if rec.result == "1-0")
    losses = sum(1 for rec in records if rec.result == "0-1")
    draws = sum(1 for rec in records if rec.result == "1/2-1/2")

    total_moves = sum(len(rec.moves) for rec in records)
    illegal_raw = sum(
        1
        for rec in records
        for move in rec.moves
        if not move.move_decision.parse_ok or not move.move_decision.is_legal
    )
    retries = sum(rec_move.move_decision.retry_count for rec in records for rec_move in rec.moves)
    retry_success = sum(
        1
        for rec in records
        for rec_move in rec.moves
        if rec_move.move_decision.retry_count > 0 and rec_move.move_decision.is_legal
    )
    retrieval_enabled_moves = sum(
        1
        for rec in records
        for rec_move in rec.moves
        if rec_move.move_decision.retrieval_enabled
    )
    retrieval_hit_moves = sum(
        1
        for rec in records
        for rec_move in rec.moves
        if rec_move.move_decision.retrieval_enabled
        and rec_move.move_decision.retrieval_hit_count > 0
    )
    retrieval_hits_total = sum(
        rec_move.move_decision.retrieval_hit_count
        for rec in records
        for rec_move in rec.moves
        if rec_move.move_decision.retrieval_enabled
    )
    retrieval_latency_total = sum(
        rec_move.move_decision.retrieval_latency_ms
        for rec in records
        for rec_move in rec.moves
        if rec_move.move_decision.retrieval_enabled
    )
    retrieval_phase_totals = {"opening": 0, "middlegame": 0, "endgame": 0}
    retrieval_phase_hits = {"opening": 0, "middlegame": 0, "endgame": 0}
    for rec in records:
        for rec_move in rec.moves:
            decision = rec_move.move_decision
            phase = (decision.retrieval_phase or "").strip().lower()
            if phase not in retrieval_phase_totals:
                continue
            if not decision.retrieval_enabled:
                continue
            retrieval_phase_totals[phase] += 1
            if decision.retrieval_hit_count > 0:
                retrieval_phase_hits[phase] += 1
    moa_moves = sum(
        1
        for rec in records
        for rec_move in rec.moves
        if rec_move.move_decision.decision_mode == "capability_moa"
    )
    games_with_provider_timeout = 0
    for rec in records:
        if rec.termination in NON_VALID_TERMINATIONS:
            nonvalid_games += 1
        else:
            valid_games += 1
        if _record_has_provider_timeout(rec):
            games_with_provider_timeout += 1
    completion_rate = valid_games / scheduled_games if scheduled_games else 0.0
    total_games = valid_games if valid_games else 1

    token_total = sum(rec.token_usage["input"] + rec.token_usage["output"] for rec in records)
    cost_total = sum(rec.cost_usd for rec in records)
    latencies_ms = [
        move.move_decision.latency_ms for rec in records for move in rec.moves if move.move_decision.latency_ms >= 0
    ]
    p95_latency = _p95(latencies_ms)
    timeout_games = sum(1 for rec in records if rec.termination == "timeout")
    timeout_rate = (timeout_games / total_records) if total_records else 0.0
    budget_utilization = None
    if budget_cap_usd is not None and budget_cap_usd > 0:
        budget_utilization = cost_total / budget_cap_usd
    provider_timeout_game_rate = (games_with_provider_timeout / total_records) if total_records else 0.0
    nonvalid_game_rate = (nonvalid_games / total_records) if total_records else 0.0
    retrieval_hit_rate = (
        retrieval_hit_moves / retrieval_enabled_moves if retrieval_enabled_moves else 0.0
    )
    avg_retrieval_hits_per_move = (
        retrieval_hits_total / total_moves if total_moves else 0.0
    )
    avg_retrieval_latency_ms = (
        retrieval_latency_total / retrieval_enabled_moves if retrieval_enabled_moves else 0.0
    )
    retrieval_hit_rate_by_phase = {
        phase: (
            retrieval_phase_hits[phase] / retrieval_phase_totals[phase]
            if retrieval_phase_totals[phase]
            else 0.0
        )
        for phase in ("opening", "middlegame", "endgame")
    }
    moa_move_share = (moa_moves / total_moves) if total_moves else 0.0

    return ExperimentReport(
        schema_version="1.0",
        experiment_id=experiment_id,
        config_hash=config_hash,
        num_games_target=target_games,
        num_games_scheduled=scheduled_games,
        num_games_valid=valid_games,
        completion_rate=completion_rate,
        wins=wins,
        draws=draws,
        losses=losses,
        win_loss_score=0.5 * (((wins - losses) / total_games) + 1.0),
        elo_estimate=None,
        elo_ci_95=None,
        acpl_overall=0.0,
        acpl_by_phase={"opening": 0.0, "middlegame": 0.0, "endgame": 0.0},
        blunder_rate=0.0,
        best_move_agreement=0.0,
        illegal_move_rate_raw=(illegal_raw / total_moves) if total_moves else 0.0,
        retry_success_rate=(retry_success / retries) if retries else 0.0,
        avg_tokens_per_move=(token_total / total_moves) if total_moves else 0.0,
        avg_cost_per_game=(cost_total / valid_games) if valid_games else 0.0,
        p95_move_latency_ms=p95_latency,
        timeout_rate=timeout_rate,
        total_cost_usd=cost_total,
        budget_cap_usd=budget_cap_usd,
        budget_utilization=budget_utilization,
        stopped_due_to_budget=stopped_due_to_budget,
        budget_stop_reason=budget_stop_reason,
        stopped_due_to_reliability=stopped_due_to_reliability,
        reliability_stop_reason=reliability_stop_reason,
        provider_timeout_game_rate=provider_timeout_game_rate,
        nonvalid_game_rate=nonvalid_game_rate,
        retrieval_hit_rate=retrieval_hit_rate,
        avg_retrieval_hits_per_move=avg_retrieval_hits_per_move,
        avg_retrieval_latency_ms=avg_retrieval_latency_ms,
        retrieval_hit_rate_by_phase=retrieval_hit_rate_by_phase,
        moa_move_share=moa_move_share,
    )


def _p95(values: list[int]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    idx = math.ceil(0.95 * len(sorted_values)) - 1
    idx = max(0, min(idx, len(sorted_values) - 1))
    return float(sorted_values[idx])


def _record_has_provider_timeout(record: GameRecord) -> bool:
    for move in record.moves:
        error = move.move_decision.error
        if isinstance(error, str) and error.startswith("provider_timeout"):
            return True
    return False
