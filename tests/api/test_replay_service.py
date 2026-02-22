from __future__ import annotations

from zugzwang.api.services.replay_service import ReplayService
from zugzwang.api.types import GameRecordView


def _sample_game() -> GameRecordView:
    return GameRecordView(
        game_number=1,
        result="*",
        termination="max_moves",
        duration_seconds=10.0,
        total_cost_usd=0.01,
        total_tokens={"input": 10, "output": 20},
        moves=[
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
                    "feedback_level": "rich",
                    "cost_usd": 0.0,
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
                    "retry_count": 1,
                    "tokens_input": 50,
                    "tokens_output": 25,
                    "latency_ms": 100,
                    "provider_model": "glm-5",
                    "feedback_level": "rich",
                    "cost_usd": 0.001,
                },
            },
        ],
    )


def test_build_board_states_returns_initial_plus_plies() -> None:
    replay = ReplayService()
    frames = replay.build_board_states(_sample_game())

    assert len(frames) == 3
    assert frames[0].ply_number == 0
    assert frames[1].move_san == "e4"
    assert frames[2].move_san == "e5"


def test_frame_metrics_returns_move_level_metrics() -> None:
    replay = ReplayService()
    metrics = replay.frame_metrics(_sample_game(), ply=2)

    assert metrics.tokens_input == 50
    assert metrics.tokens_output == 25
    assert metrics.retry_count == 1
    assert metrics.provider_model == "glm-5"

