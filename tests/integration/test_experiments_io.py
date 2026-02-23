from __future__ import annotations

from zugzwang.experiments.io import game_record_from_dict


def test_game_record_from_dict_preserves_null_move_uci() -> None:
    payload = {
        "experiment_id": "exp",
        "game_number": 1,
        "config_hash": "hash",
        "seed": 42,
        "players": {},
        "moves": [
            {
                "ply_number": 1,
                "color": "black",
                "fen_before": "fen",
                "move_decision": {
                    "move_uci": None,
                    "move_san": "",
                    "raw_response": "invalid",
                    "parse_ok": False,
                    "is_legal": False,
                    "retry_count": 3,
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "latency_ms": 0,
                    "provider_model": "mock",
                },
            }
        ],
        "result": "*",
        "termination": "error",
        "token_usage": {"input": 0, "output": 0},
        "cost_usd": 0.0,
        "duration_seconds": 0.1,
        "timestamp_utc": "2026-02-23T00:00:00Z",
    }

    record = game_record_from_dict(payload)

    assert record.moves[0].move_decision.move_uci is None
