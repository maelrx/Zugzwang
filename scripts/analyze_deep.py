"""Deep post-hoc Stockfish analysis over finished runs (official DB path).

Drives the versioned StockfishEvaluator with a REAL UCI engine and persists
metric observations + evaluation_runs rows via EvaluateRunService — the run
itself is never altered. Nothing here is shown to the model during play.

Usage:
    uv run python scripts/analyze_deep.py --run run_XXX [--run run_YYY]
    uv run python scripts/analyze_deep.py --all-completed
    uv run python scripts/analyze_deep.py --all-completed --depth 18 --threads 14 --hash-mb 8192 --multipv 3

--all-completed skips runs that already have a COMPLETED evaluation with the
same evaluator id + depth, or a RUNNING one (another worker got there first).
Idempotent; safe to run on a loop or concurrently — re-run safely.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

STOCKFISH = "/home/maelrx/.local/bin/stockfish"
EVALUATOR_ID = "evaluator.stockfish"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def already_evaluated(services: object, run_id: str, depth: int) -> bool:
    from typing import Any

    from zugzwang_runtime.persistence.repositories import EvaluationRunRepository

    engine: Any = getattr(services, "database_engine")
    repo = EvaluationRunRepository(engine)
    rows: Any = repo.for_run(run_id)
    for row in rows:
        if row["evaluator_id"] != EVALUATOR_ID:
            continue
        if row["status"] == "RUNNING":
            return True  # another worker is on it; do not duplicate
        if row["status"] != "COMPLETED":
            continue
        try:
            engine_json: Any = row["engine_json"] or {}
            if isinstance(engine_json, str):
                engine_json = json.loads(engine_json)
            meta: Any = engine_json.get("engine", engine_json)
            limit: Any = meta.get("limit", {})
            if int(limit.get("depth", -1)) >= depth:
                return True
        except (ValueError, TypeError, AttributeError):
            continue
    return False


async def analyze_one(
    services: object,
    run_id: str,
    *,
    depth: int,
    threads: int,
    hash_mb: int,
    multipv: int,
    engine_path: str,
) -> dict[str, object]:
    from zgw_eval_stockfish.evaluator import StockfishEvaluator
    from zgw_eval_stockfish.uci import UciEngineClient
    from zugzwang_runtime.application.evaluation import EvaluateRunService
    from zugzwang_runtime.persistence.repositories import MetricObservationRepository

    binary_sha = sha256_file(engine_path)
    engine = UciEngineClient(
        engine_path,
        options={"Threads": str(threads), "Hash": str(hash_mb)},
    )
    evaluator = StockfishEvaluator(
        engine,
        limit={"depth": depth},
        multipv=multipv,
        binary_metadata={
            "binary": engine_path,
            "sha256": binary_sha,
            "threads": threads,
            "hash_mb": hash_mb,
        },
    )
    service = EvaluateRunService(
        runs=services.runs,  # type: ignore[attr-defined]
        episodes=services.episodes,  # type: ignore[attr-defined]
        steps=services.steps,  # type: ignore[attr-defined]
        metrics=MetricObservationRepository(services.database_engine),  # type: ignore[attr-defined]
        cas=services.cas,  # type: ignore[attr-defined]
    )
    summary = await service.evaluate(run_id, evaluator, evaluator_id=EVALUATOR_ID)
    try:
        await engine.quit()
    except Exception:
        pass
    return summary.model_dump() if hasattr(summary, "model_dump") else dict(summary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", default=[], help="run id (repeatable)")
    parser.add_argument("--all-completed", action="store_true")
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="with --all-completed, also pick up FAILED runs (analyzes committed moves)",
    )
    parser.add_argument("--depth", type=int, default=20)
    parser.add_argument("--threads", type=int, default=14)
    parser.add_argument("--hash-mb", type=int, default=8192)
    parser.add_argument("--multipv", type=int, default=3)
    parser.add_argument("--engine", default=STOCKFISH)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()

    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.execution.registry import PluginRegistry
    from zugzwang_runtime.workspace import Workspace

    services = DurableRunServices(Workspace.from_root(args.workspace.resolve()), PluginRegistry())

    targets: list[str] = list(args.run)
    if args.all_completed:
        wanted = {"COMPLETED", "FAILED"} if args.include_failed else {"COMPLETED"}
        for row in services.runs.list_runs(limit=500):
            if row.get("status") not in wanted:
                continue
            run_id = str(row["run_id"])
            if already_evaluated(services, run_id, args.depth):
                print(f"skip {run_id} (already evaluated at depth>={args.depth})")
                continue
            targets.append(run_id)
    if not targets:
        print("nothing to analyze")
        return 0

    print(
        f"deep analysis: depth={args.depth} threads={args.threads} "
        f"hash={args.hash_mb}MB multipv={args.multipv} runs={len(targets)}"
    )
    failed = 0
    for run_id in targets:
        try:
            summary = asyncio.run(
                analyze_one(
                    services,
                    run_id,
                    depth=args.depth,
                    threads=args.threads,
                    hash_mb=args.hash_mb,
                    multipv=args.multipv,
                    engine_path=args.engine,
                )
            )
            obs = summary.get("observations", summary.get("total_observations", "?"))
            print(f"done {run_id}: observations={obs}")
        except Exception as exc:  # noqa: BLE001 — report and continue with next run
            failed += 1
            print(f"FAILED {run_id}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
