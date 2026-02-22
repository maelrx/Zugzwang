from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zugzwang.core.models import GameRecord, MoveDecision, MoveRecord


def game_record_from_dict(payload: dict[str, Any]) -> GameRecord:
    moves: list[MoveRecord] = []
    for move_payload in payload.get("moves", []):
        decision_payload = move_payload.get("move_decision", {})
        decision = MoveDecision(
            move_uci=str(decision_payload.get("move_uci", "")),
            move_san=str(decision_payload.get("move_san", "")),
            raw_response=str(decision_payload.get("raw_response", "")),
            parse_ok=bool(decision_payload.get("parse_ok", False)),
            is_legal=bool(decision_payload.get("is_legal", False)),
            retry_count=int(decision_payload.get("retry_count", 0)),
            tokens_input=int(decision_payload.get("tokens_input", 0)),
            tokens_output=int(decision_payload.get("tokens_output", 0)),
            latency_ms=int(decision_payload.get("latency_ms", 0)),
            provider_model=str(decision_payload.get("provider_model", "")),
            provider_calls=int(decision_payload.get("provider_calls", 0)),
            feedback_level=str(decision_payload.get("feedback_level", "rich")),
            error=decision_payload.get("error"),
            cost_usd=float(decision_payload.get("cost_usd", 0.0)),
            retrieval_enabled=bool(decision_payload.get("retrieval_enabled", False)),
            retrieval_hit_count=int(decision_payload.get("retrieval_hit_count", 0)),
            retrieval_latency_ms=int(decision_payload.get("retrieval_latency_ms", 0)),
            retrieval_sources=(
                [
                    str(source)
                    for source in decision_payload.get("retrieval_sources", [])
                    if isinstance(source, str)
                ]
                if isinstance(decision_payload.get("retrieval_sources"), list)
                else []
            ),
            retrieval_phase=(
                str(decision_payload.get("retrieval_phase"))
                if decision_payload.get("retrieval_phase") is not None
                else None
            ),
            decision_mode=str(decision_payload.get("decision_mode", "single_agent")),
            agent_trace=(
                list(decision_payload.get("agent_trace", []))
                if isinstance(decision_payload.get("agent_trace"), list)
                else []
            ),
        )
        moves.append(
            MoveRecord(
                ply_number=int(move_payload.get("ply_number", 0)),
                color=str(move_payload.get("color", "")),
                fen_before=str(move_payload.get("fen_before", "")),
                move_decision=decision,
            )
        )

    return GameRecord(
        experiment_id=str(payload.get("experiment_id", "")),
        game_number=int(payload.get("game_number", 0)),
        config_hash=str(payload.get("config_hash", "")),
        seed=int(payload.get("seed", 0)),
        players=payload.get("players", {}),
        moves=moves,
        result=str(payload.get("result", "*")),
        termination=str(payload.get("termination", "unknown")),
        token_usage={
            "input": int(payload.get("token_usage", {}).get("input", 0)),
            "output": int(payload.get("token_usage", {}).get("output", 0)),
        },
        cost_usd=float(payload.get("cost_usd", 0.0)),
        duration_seconds=float(payload.get("duration_seconds", 0.0)),
        timestamp_utc=str(payload.get("timestamp_utc", "")),
    )


def game_record_to_dict(record: GameRecord) -> dict[str, Any]:
    return record.to_dict()


def load_game_record(path: str | Path) -> GameRecord:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return game_record_from_dict(raw)


def load_game_records(games_dir: str | Path) -> list[GameRecord]:
    games_path = Path(games_dir)
    records: list[GameRecord] = []
    for file_path in sorted(games_path.glob("game_*.json")):
        records.append(load_game_record(file_path))
    return records
