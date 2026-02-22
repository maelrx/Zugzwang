from __future__ import annotations

from zugzwang.core.models import GameRecord, MoveDecision, MoveRecord
from zugzwang.evaluation.metrics import summarize_experiment


def _move(
    *,
    ply: int,
    retrieval_enabled: bool,
    retrieval_hit_count: int,
    retrieval_latency_ms: int,
    retrieval_phase: str,
    decision_mode: str,
) -> MoveRecord:
    return MoveRecord(
        ply_number=ply,
        color="black" if ply % 2 == 0 else "white",
        fen_before="",
        move_decision=MoveDecision(
            move_uci="e2e4",
            move_san="e4",
            raw_response="e2e4",
            parse_ok=True,
            is_legal=True,
            retry_count=0,
            tokens_input=10,
            tokens_output=2,
            latency_ms=7,
            provider_model="mock-1",
            retrieval_enabled=retrieval_enabled,
            retrieval_hit_count=retrieval_hit_count,
            retrieval_latency_ms=retrieval_latency_ms,
            retrieval_sources=["eco"],
            retrieval_phase=retrieval_phase,
            decision_mode=decision_mode,
        ),
    )


def test_summarize_experiment_includes_retrieval_and_moa_metrics() -> None:
    record = GameRecord(
        experiment_id="exp",
        game_number=1,
        config_hash="hash",
        seed=42,
        players={"white": {"type": "random"}, "black": {"type": "llm"}},
        moves=[
            _move(
                ply=1,
                retrieval_enabled=True,
                retrieval_hit_count=2,
                retrieval_latency_ms=5,
                retrieval_phase="opening",
                decision_mode="capability_moa",
            ),
            _move(
                ply=2,
                retrieval_enabled=True,
                retrieval_hit_count=0,
                retrieval_latency_ms=4,
                retrieval_phase="opening",
                decision_mode="single_agent",
            ),
            _move(
                ply=3,
                retrieval_enabled=True,
                retrieval_hit_count=1,
                retrieval_latency_ms=6,
                retrieval_phase="endgame",
                decision_mode="capability_moa",
            ),
        ],
        result="0-1",
        termination="checkmate",
        token_usage={"input": 30, "output": 6},
        cost_usd=0.03,
        duration_seconds=1.2,
        timestamp_utc="2026-02-22T00:00:00Z",
    )

    report = summarize_experiment(
        experiment_id="exp",
        config_hash="hash",
        target_games=1,
        scheduled_games=1,
        game_records=[record],
    )

    assert report.completion_rate == 1.0
    assert report.retrieval_hit_rate == 2 / 3
    assert report.avg_retrieval_hits_per_move == 1.0
    assert report.avg_retrieval_latency_ms == 5.0
    assert report.retrieval_hit_rate_by_phase["opening"] == 0.5
    assert report.retrieval_hit_rate_by_phase["endgame"] == 1.0
    assert report.moa_move_share == 2 / 3
