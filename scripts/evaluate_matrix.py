"""Run the NATIVE post-hoc Stockfish evaluator (depth 20, real UCI engine)
over finished matrix runs, so the webUI Analysis tab renders official metrics.

Usage: uv run python scripts/evaluate_matrix.py
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from zgw_eval_stockfish.evaluator import StockfishEvaluator
from zgw_eval_stockfish.uci import UciEngineClient

from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.evaluation import EvaluateRunService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import MetricObservationRepository
from zugzwang_runtime.workspace import Workspace

SF = "/home/maelrx/.local/bin/stockfish"
MATRIX = ["b", "f", "g", "h", "i", "j", "k", "l", "e", "a", "c", "d"]


def run_id_for(ws: str) -> str | None:
    conn = sqlite3.connect(f"{ws}/.zugzwang/state.db")
    row = conn.execute(
        "SELECT run_id FROM runs WHERE status IN ('COMPLETED','FAILED','CANCELED') "
        "ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


async def evaluate_one(ws: str, run_id: str, evaluator: StockfishEvaluator) -> dict:
    services = DurableRunServices(Workspace.from_root(Path(ws)), PluginRegistry())
    engine = services.database_engine
    summary = await EvaluateRunService(
        runs=services.runs,
        episodes=services.episodes,
        steps=services.steps,
        metrics=MetricObservationRepository(engine),
        cas=services.cas,
    ).evaluate(run_id, evaluator, evaluator_id="evaluator.stockfish")
    return summary


async def main() -> None:
    engine = UciEngineClient(SF, options={"Threads": "4", "Hash": "512"})
    await engine.start()
    evaluator = StockfishEvaluator(
        engine,
        limit={"depth": 20},
        binary_metadata={"binary": SF, "depth": 20, "note": "real Stockfish 16, matrix sweep"},
    )
    try:
        for w in MATRIX:
            ws = f"/tmp/cb-arena-{w}"
            run_id = run_id_for(ws)
            if not run_id:
                print(f"== {w}: sem run, pulando", flush=True)
                continue
            print(f"== {w} ({run_id}): avaliando depth 20...", flush=True)
            try:
                summary = await evaluate_one(ws, run_id, evaluator)
                n = len(summary.get("metrics", summary) if isinstance(summary, dict) else [summary])
                print(f"   OK: {n} métricas", flush=True)
            except Exception as exc:  # keep the sweep going
                print(f"   ERRO: {str(exc)[:150]}", flush=True)
    finally:
        await engine.quit()


if __name__ == "__main__":
    asyncio.run(main())
