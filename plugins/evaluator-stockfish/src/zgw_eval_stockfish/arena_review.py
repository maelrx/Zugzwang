"""Depth-20 post-game arena review using the existing UCI process adapter."""

from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import chess

from .uci import UciEngineClient

DEPTH = 20
OPTIONS = {"Threads": "2", "Hash": "128", "UCI_LimitStrength": "false", "Skill Level": "20"}


class StockfishArenaReview:
    def __init__(self, executable: str = "stockfish") -> None:
        self.executable = shutil.which(executable) or executable
        path = Path(self.executable)
        self.profile: dict[str, Any] = {
            "evaluator": "arena.stockfish/1.0.0",
            "depth": DEPTH,
            "options": dict(OPTIONS),
            "multipv": 1,
            "perspective": "white",
            "executable_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file()
            else None,
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "regime": "post_game",
        }

    def __call__(self, source: dict[str, Any], completed: int) -> Iterator[dict[str, Any]]:
        board = chess.Board(source["start_fen"])
        moves = source["moves"]
        client = UciEngineClient(self.executable, options=OPTIONS)
        with asyncio.Runner() as runner:
            try:
                metadata = runner.run(asyncio.wait_for(client.start(), timeout=20))
                for ply in range(len(moves) + 1):
                    if ply:
                        move = chess.Move.from_uci(moves[ply - 1])
                        if move not in board.legal_moves:
                            raise ValueError(f"Illegal recorded move at ply {ply}")
                        board.push(move)
                    if ply < completed:
                        continue
                    row: dict[str, Any] = {
                        "ply": ply,
                        "fen": board.fen(),
                        "engine": metadata.name,
                        "requested_depth": DEPTH,
                        "depth": None,
                        "cp_white": None,
                        "mate_white": None,
                        "best_uci": None,
                        "best_san": None,
                        "pv_san": [],
                    }
                    outcome = board.outcome(claim_draw=False)
                    if outcome:
                        row.update(
                            terminal=outcome.termination.name.lower(),
                            winner="white"
                            if outcome.winner
                            else "black"
                            if outcome.winner is not None
                            else None,
                            cp_white=0 if outcome.winner is None else None,
                            mate_white=0 if board.is_checkmate() else None,
                            raw_uci=[],
                        )
                        yield row
                        continue
                    runner.run(client.position(source["start_fen"], moves[:ply]))
                    result = runner.run(asyncio.wait_for(client.go({"depth": DEPTH}), timeout=180))
                    if not result.lines:
                        raise ValueError(f"Stockfish returned no score at ply {ply}")
                    line = result.lines[0]
                    depths = [
                        int(m.group(1))
                        for text in result.raw_transcript
                        if (m := re.search(r"\bdepth (\d+)", text))
                    ]
                    depth = max(depths, default=0)
                    if depth < DEPTH and line.score.kind != "mate":
                        raise ValueError(f"Incomplete analysis at ply {ply}: depth {depth}/{DEPTH}")
                    sign = 1 if board.turn else -1
                    row.update(
                        depth=depth,
                        cp_white=line.score.value * sign if line.score.kind == "cp" else None,
                        mate_white=line.score.value * sign if line.score.kind == "mate" else None,
                        best_uci=result.bestmove,
                        raw_uci=list(result.raw_transcript),
                    )
                    variation = board.copy()
                    pv_san: list[str] = []
                    for uci in line.pv[:12]:
                        move = chess.Move.from_uci(uci)
                        if move not in variation.legal_moves:
                            raise ValueError("Stockfish returned an illegal principal variation")
                        pv_san.append(variation.san(move))
                        variation.push(move)
                    row["pv_san"] = pv_san
                    if result.bestmove:
                        row["best_san"] = board.san(chess.Move.from_uci(result.bestmove))
                    yield row
            finally:
                runner.run(client.quit())
