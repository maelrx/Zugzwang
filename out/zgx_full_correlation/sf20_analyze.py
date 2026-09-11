#!/usr/bin/env python3
"""Uniform SF-d20 game analyzer for the ZGX correlation study.

Replicates byte-for-byte the established record convention (live watcher + R1):
  cp_before = mover-pov eval of the pre-position at depth 20
  cp_after  = mover-pov eval of the post-move position at depth 20
  regret    = cp_before - cp_after (raw, may be slightly negative)
  best_move = pv[0] of the pre-position search; agreement = played == best
  blunder   = regret >= 300
Mate scores clamp to ±10000. Two searches per ply, Threads=1 (deterministic).

Usage: sf20_analyze.py <pgn> <out.json> [engine_path]
"""
from __future__ import annotations

import json
import sys
import chess
import chess.pgn
from chess.engine import SimpleEngine, Limit

MATE_CLAMP = 10000
BLUNDER_CP = 300


def score_cp(score, pov: chess.Color) -> int:
    s = score.pov(pov)
    if s.is_mate():
        n = s.mate()
        return MATE_CLAMP - abs(n) if n > 0 else -(MATE_CLAMP - abs(n))
    return int(s.score())


def analyze_game(game, engine) -> dict:
    board = game.board()
    records = []
    traj = []
    ply = 0
    node = game
    while node.variations:
        node = node.variation(0)
        move = node.move
        if move is None:
            break
        ply += 1
        side = "white" if board.turn else "black"
        pov = board.turn
        san = board.san(move)

        info = engine.analyse(board, Limit(depth=20))
        cp_before = score_cp(info["score"], pov)
        best_move = (info.get("pv") or [move])[0].uci()

        board.push(move)
        reply = engine.analyse(board, Limit(depth=20))
        cp_after = -score_cp(reply["score"], not pov)

        regret = cp_before - cp_after
        records.append({
            "ply": ply,
            "uci": move.uci(),
            "san": san,
            "side": side,
            "cp_before": cp_before,
            "cp_after": cp_after,
            "regret": regret,
            "best_move": best_move,
            "agreement": move.uci() == best_move,
            "blunder": regret >= BLUNDER_CP,
            "mate": info["score"].pov(pov).is_mate() or reply["score"].pov(not pov).is_mate(),
        })
        traj.append(cp_after if side == "white" else -cp_after)

    def side_stats(side: str) -> dict:
        rs = [r["regret"] for r in records if r["side"] == side]
        if not rs:
            return {}
        capped = [min(max(r, 0), 1000) for r in rs]
        return {
            "moves": len(rs),
            "acpl": round(sum(capped) / len(capped), 1),
            "blunders": sum(1 for r in rs if r >= BLUNDER_CP),
            "cliffs": sum(1 for r in rs if r >= 1000),
            "agreement": round(sum(1 for r in records if r["side"] == side and r["agreement"]) / len(rs), 3),
        }

    return {
        "headers": dict(game.headers),
        "result": game.headers.get("Result", "*"),
        "plies": ply,
        "white": side_stats("white"),
        "black": side_stats("black"),
        "records": records,
        "eval_trajectory_white_pov": traj,
    }


def main() -> None:
    pgn_path, out_path = sys.argv[1], sys.argv[2]
    engine_path = sys.argv[3] if len(sys.argv) > 3 else "/home/maelrx/.local/bin/stockfish"
    engine = SimpleEngine.popen_uci(engine_path)
    engine.configure({"Threads": 1, "Hash": 64})
    games = []
    with open(pgn_path) as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            games.append(game)
    results = [analyze_game(g, engine) for g in games]
    engine.quit()
    with open(out_path, "w") as handle:
        json.dump({"source_pgn": pgn_path, "engine": "stockfish-16", "depth": 20,
                   "games": results}, handle, indent=1)
    for g in results:
        print(f"{pgn_path.split('/')[-1]}: {g['result']} plies={g['plies']} "
              f"W={g['white'].get('acpl')}({g['white'].get('blunders')}b) "
              f"B={g['black'].get('acpl')}({g['black'].get('blunders')}b)", flush=True)


if __name__ == "__main__":
    main()
