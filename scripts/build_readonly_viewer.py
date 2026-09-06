"""Build a redacted, read-only browser snapshot from a Zugzwang workspace.

The browser never opens SQLite or the CAS. This script is the only bridge: it
reads projections/artifacts and emits a small ``viewer/data.js`` snapshot.
No request/response bodies are copied, and secret-looking config keys are
redacted before serialization.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chess
from chess.svg import PIECES as SVG_PIECES

from zugzwang_core.domain.artifacts import ArtifactRef
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.execution.registry import PluginRegistry
from zugzwang_runtime.persistence.repositories import AttemptRepository, MetricObservationRepository
from zugzwang_runtime.workspace import Workspace

_SECRET_KEY_NAMES = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
    "authorization",
    "bearer",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized_key = key_text.lower().replace("-", "_")
            is_secret_key = (
                normalized_key in _SECRET_KEY_NAMES
                or normalized_key.endswith("_key")
                or "password" in normalized_key
                or normalized_key.startswith("authorization")
            )
            if is_secret_key:
                result[key_text] = "[redacted]"
            else:
                result[key_text] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _artifact_json(services: DurableRunServices, ref: Any) -> dict[str, Any]:
    if not isinstance(ref, str) or not ref:
        return {}
    try:
        raw = services.cas.get(ArtifactRef.parse(ref)).data.decode("utf-8")
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _resolved_condition(services: DurableRunServices, run: dict[str, Any]) -> dict[str, Any]:
    resolved = _artifact_json(services, run.get("resolved_manifest_artifact_id"))
    for condition in resolved.get("conditions", []):
        if isinstance(condition, dict) and condition.get("condition_id") == run.get("condition_id"):
            return condition
    source = resolved.get("source")
    if isinstance(source, dict):
        spec = source.get("spec")
        if isinstance(spec, dict):
            return spec
    return {}


def _side_from_fen(fen: str | None) -> str:
    if not isinstance(fen, str):
        return "?"
    fields = fen.split()
    return "White" if len(fields) > 1 and fields[1] == "w" else "Black"


def _san_for(fen: str | None, uci: Any) -> str | None:
    if not isinstance(fen, str) or not isinstance(uci, str):
        return None
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        return board.san(move) if board.is_legal(move) else None
    except (ValueError, chess.InvalidMoveError):
        return None


def _actor_kind(actor: str, policy: dict[str, Any] | None) -> str:
    if policy:
        policy_id = str(policy.get("policy_id") or actor)
        if policy_id.startswith("chess.stockfish"):
            return "Stockfish"
        if policy_id.startswith("chess.random"):
            return "Random"
        return "Opponent"
    if actor.startswith("model-opponent/"):
        return "Model opponent"
    return "Model"


def _episode_snapshot(
    services: DurableRunServices,
    episode: dict[str, Any],
    step_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    initial = _artifact_json(services, episode.get("initial_state_artifact_id"))
    initial_fen = initial.get("fen") if isinstance(initial.get("fen"), str) else None
    positions: list[dict[str, Any]] = [
        {
            "ply": 0,
            "fen": initial_fen,
            "moves": list(initial.get("moves") or []),
            "terminal": False,
        }
    ]
    moves: list[dict[str, Any]] = []
    previous_fen = initial_fen
    for row in step_rows:
        if row.get("status") != "COMMITTED":
            continue
        action_json = row.get("action_json") or {}
        action = action_json.get("action") if isinstance(action_json, dict) else None
        kind = action_json.get("kind") if isinstance(action_json, dict) else None
        policy = action_json.get("policy") if isinstance(action_json, dict) else None
        policy = _redact(policy) if isinstance(policy, dict) else None
        after = _artifact_json(services, row.get("transition_artifact_id"))
        fen_after = after.get("fen") if isinstance(after.get("fen"), str) else previous_fen
        uci = action if isinstance(action, str) and not kind else None
        moves.append(
            {
                "ply": len(moves) + 1,
                "side": _side_from_fen(previous_fen),
                "moveNumber": (
                    int(previous_fen.split()[5])
                    if isinstance(previous_fen, str) and len(previous_fen.split()) > 5
                    else 1
                ),
                "uci": uci,
                "san": _san_for(previous_fen, uci),
                "display": str(action) if action is not None else "(sem ação)",
                "kind": kind,
                "actor": str(row.get("actor_id") or "unknown"),
                "actorKind": _actor_kind(str(row.get("actor_id") or "unknown"), policy),
                "policy": policy,
                "stepId": row.get("step_id"),
                "fenAfter": fen_after,
                "terminal": bool(after.get("terminal", False)),
            }
        )
        positions.append(
            {
                "ply": len(moves),
                "fen": fen_after,
                "moves": list(after.get("moves") or []),
                "terminal": bool(after.get("terminal", False)),
            }
        )
        previous_fen = fen_after

    final_fen = positions[-1].get("fen")
    result = "in_progress"
    winner: str | None = None
    try:
        board = chess.Board(final_fen) if isinstance(final_fen, str) else None
        if board is not None and board.is_checkmate():
            result = "checkmate"
            winner = "Black" if board.turn == chess.WHITE else "White"
        elif board is not None and board.is_stalemate():
            result = "stalemate"
        elif episode.get("status") == "FAILED":
            result = "failed"
        else:
            result = "capped"
    except (ValueError, chess.InvalidFenError):
        result = "unknown"

    return {
        "id": episode.get("episode_id"),
        "ordinal": episode.get("ordinal"),
        "status": episode.get("status"),
        "outcome": episode.get("outcome"),
        "stepsCommitted": len(moves),
        "stepsFailed": sum(row.get("status") == "TERMINAL_FAILURE" for row in step_rows),
        "result": result,
        "winner": winner,
        "positions": positions,
        "moves": moves,
    }


def _players(condition: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for side, player in (condition.get("players") or {}).items():
        if not isinstance(player, dict):
            continue
        model = player.get("model")
        policy = player.get("policy")
        result.append(
            {
                "side": str(side).title(),
                "model": _redact(model) if isinstance(model, dict) else None,
                "policy": _redact(policy) if isinstance(policy, dict) else None,
            }
        )
    return result


def _build_run(services: DurableRunServices, run: dict[str, Any]) -> dict[str, Any]:
    condition = _resolved_condition(services, run)
    episodes: list[dict[str, Any]] = []
    all_steps: list[dict[str, Any]] = []
    for episode in services.episodes.for_run(str(run["run_id"])):
        rows = services.steps.for_episode(str(episode["episode_id"]))
        all_steps.extend(rows)
        episodes.append(_episode_snapshot(services, episode, rows))

    events = services.events.for_run(str(run["run_id"]))
    provider_completed = [e for e in events if e.get("event_type") == "provider.call.completed"]
    provider_failures = [
        e
        for e in events
        if e.get("event_type") in {"provider.call.failed", "provider.call.timeout_unknown"}
    ]
    tokens = {"input": 0, "output": 0}
    for event in provider_completed:
        usage = (event.get("payload_json") or {}).get("usage") or {}
        tokens["input"] += int(usage.get("input_tokens", 0) or 0)
        tokens["output"] += int(usage.get("output_tokens", 0) or 0)

    metrics_repo = MetricObservationRepository(services.database_engine)
    raw_metrics = metrics_repo.for_run(str(run["run_id"]))
    precise_candidates = [
        row
        for row in raw_metrics
        if row.get("evaluator_id") == "evaluator.stockfish.precise"
        or row.get("evaluator_version") in {"0.2.0", "0.3.0"}
    ]
    precise_versions = {
        str(row.get("evaluator_version"))
        for row in precise_candidates
        if row.get("evaluator_version")
    }
    latest_precise_version = max(
        precise_versions,
        key=lambda value: tuple(int(part) for part in value.split(".")),
        default=None,
    )
    precise_metrics = [
        row for row in precise_candidates if row.get("evaluator_version") == latest_precise_version
    ]
    selected_metrics = precise_metrics or raw_metrics
    metrics = [
        {
            "id": row.get("metric_observation_id"),
            "metric": row.get("metric_definition_id"),
            "version": row.get("metric_version"),
            "valueNum": row.get("value_num"),
            "valueText": row.get("value_text"),
            "unit": row.get("unit"),
            "dimensions": _redact(row.get("dimensions_json") or {}),
            "evaluator": row.get("evaluator_id"),
            "episodeId": row.get("episode_id"),
            "stepId": row.get("step_id"),
        }
        for row in selected_metrics
    ]

    attempt_repo = AttemptRepository(services.database_engine)
    cost_entries: list[dict[str, Any]] = []
    for step in all_steps:
        for attempt in attempt_repo.for_step(str(step["step_id"])):
            if attempt.get("cost_json"):
                cost_entries.append(_redact(attempt["cost_json"]))

    task = condition.get("task") if isinstance(condition.get("task"), dict) else {}
    task_config = task.get("config") if isinstance(task.get("config"), dict) else {}
    model_players = [p for p in _players(condition) if p.get("model")]
    policy_players = [p for p in _players(condition) if p.get("policy")]
    source = _artifact_json(services, run.get("resolved_manifest_artifact_id"))
    source_meta = source.get("source", {}).get("metadata", {}) if isinstance(source, dict) else {}

    return {
        "id": run.get("run_id"),
        "status": run.get("status"),
        "conditionId": run.get("condition_id"),
        "experiment": source_meta.get("name") or "Zugzwang run",
        "tags": list(source_meta.get("tags") or []),
        "protocolHash": run.get("protocol_hash"),
        "startedAt": run.get("started_at"),
        "finishedAt": run.get("finished_at"),
        "declaredAssistance": run.get("declared_assistance"),
        "effectiveAssistance": run.get("effective_assistance"),
        "players": _players(condition),
        "model": model_players[0].get("model") if model_players else None,
        "opponents": policy_players,
        "task": _redact(task_config),
        "budget": _redact(condition.get("budget") or {}),
        "provider": {
            "calls": len(provider_completed),
            "failures": len(provider_failures),
            "tokens": tokens,
            "costStatus": "reported" if cost_entries else "unknown",
            "costEntries": cost_entries,
        },
        "episodes": episodes,
        "metrics": metrics,
        "events": [
            {
                "type": event.get("event_type"),
                "at": event.get("occurred_at"),
                "payload": _redact(event.get("payload_json") or {}),
                "artifactCount": len(event.get("artifact_refs_json") or []),
            }
            for event in events
        ],
    }


def build_snapshot(workspace_root: Path, *, completed_only: bool = False) -> dict[str, Any]:
    services = DurableRunServices(Workspace.from_root(workspace_root), PluginRegistry())
    run_rows = services.runs.list_runs(limit=200)
    if completed_only:
        run_rows = [run for run in run_rows if run.get("status") == "COMPLETED"]
    runs = [_build_run(services, run) for run in run_rows]
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "workspace": str(workspace_root.resolve()),
        "readOnly": True,
        "runs": runs,
    }


def write_piece_asset(output: Path) -> None:
    """Materialize python-chess's standard Cburnett-style SVG piece set."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "window.ZUGZWANG_PIECES = "
        + json.dumps(SVG_PIECES, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("viewer/data.js"))
    parser.add_argument("--pieces", type=Path, default=Path("viewer/pieces.js"))
    parser.add_argument(
        "--completed-only",
        action="store_true",
        help="include only completed runs in the browser snapshot",
    )
    args = parser.parse_args()
    snapshot = build_snapshot(args.workspace.resolve(), completed_only=args.completed_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "window.ZUGZWANG_DATA = "
        + json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    write_piece_asset(args.pieces)
    print(
        f"viewer snapshot: {len(snapshot['runs'])} runs -> {args.output}; pieces -> {args.pieces}"
    )


if __name__ == "__main__":
    main()
