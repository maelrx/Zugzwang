"""Attach real, post-hoc Stockfish observations to one finished run."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from zgw_eval_stockfish.evaluator import StockfishEvaluator
from zgw_eval_stockfish.uci import UciEngineClient

from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.evaluation import EvaluateRunService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import MetricObservationRepository
from zugzwang_runtime.workspace import Workspace


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def evaluate(args: argparse.Namespace) -> object:
    workspace = Workspace.from_root(args.workspace.resolve())
    services = DurableRunServices(workspace, PluginRegistry())
    run = services.runs.get_run(args.run_id)
    if run is None:
        raise SystemExit(f"run not found: {args.run_id}")
    engine_path = args.engine.resolve()
    engine_options = {
        "Threads": "1",
        "Hash": "16",
        "Skill Level": str(args.skill_level),
        "UCI_ShowWDL": "true",
    }
    if args.limit_strength:
        engine_options.update(
            {
                "UCI_LimitStrength": "true",
                "UCI_Elo": str(args.elo),
            }
        )
    engine = UciEngineClient(str(engine_path), options=engine_options)
    evaluator = StockfishEvaluator(
        engine,
        limit={"nodes": args.nodes},
        multipv=args.multipv,
        binary_metadata={
            "binary": str(engine_path),
            "binary_sha256": sha256(engine_path),
            "requested_elo": args.requested_elo,
            "effective_uci_elo": args.elo if args.limit_strength else None,
            "nodes": args.nodes,
            "threads": 1,
            "hash_mb": 16,
            "multipv": args.multipv,
            "uci_show_wdl": True,
            "limit_strength": args.limit_strength,
            "skill_level": args.skill_level,
        },
    )
    # Keep corrected observations distinguishable from the legacy 0.1.0
    # evaluator already present in older workspaces.
    evaluator.evaluator_id = "evaluator.stockfish.precise"
    return await EvaluateRunService(
        runs=services.runs,
        episodes=services.episodes,
        steps=services.steps,
        metrics=MetricObservationRepository(services.database_engine),
        cas=services.cas,
    ).evaluate(args.run_id, evaluator, evaluator_id="evaluator.stockfish.precise")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--engine", type=Path, default=Path("/home/maelrx/.local/bin/stockfish"))
    parser.add_argument("--requested-elo", type=int, default=3190)
    parser.add_argument("--elo", type=int, default=3190)
    parser.add_argument("--nodes", type=int, default=20_000)
    parser.add_argument("--multipv", type=int, default=3)
    parser.add_argument("--limit-strength", action="store_true")
    parser.add_argument("--skill-level", type=int, default=20)
    result = asyncio.run(evaluate(parser.parse_args()))
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
