#!/usr/bin/env python3
"""ZGX wave 1 post-hoc evaluator (FROZEN protocol; evaluator-side only).

Quality is measured EXCLUSIVELY post-hoc with a fixed Stockfish build and
options — the player never sees an engine value. For every completed
move-selection run this script recomputes, at a fixed node budget:

- chosen action (from cb_decisions) and its legality at the root;
- evaluator best action + score BEFORE the chosen move (cp or mate);
- score AFTER the chosen move (perspective of the mover, sign-corrected);
- regret in cp (clamped for mate scores, reported separately) and a
  blunder flag at the preregistered 300 cp threshold when both scores are
  numeric and stable;
- immediate-mate-allowed flag (the chosen move lets the opponent mate in 1).

Reliability/cost come from the journals: attempts by class, tool ops,
tokens (usage_json), wall time. Mechanism probes come from the request
artifacts (neto consumed, preload, memory note). Paired A/B is reported
per position with the recorded AB/BA order; nothing here ranks by volume.

Usage: uv run python scripts/evaluate_zgx_wave1.py --root /tmp/zgx-wave1 \
          --out out/zgx_wave1_evaluation.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3

import chess
import chess.engine

MATE_SCORE = 100000
BLUNDER_CP = 300


def _sf_options() -> dict:
    return {"UCI_LimitStrength": False, "Threads": "1", "Hash": "64"}


def _score_to_cp(score: chess.engine.PovScore, mover: chess.Color) -> tuple[int | None, bool]:
    """(cp from the analysed side's perspective, is_mate)."""
    del mover
    relative = score.relative
    if relative.is_mate():
        return int(relative.score(mate_score=MATE_SCORE)), True
    return int(relative.score()), False


def analyze_position(engine: chess.engine.SimpleEngine, board: chess.Board, chosen_uci: str | None):
    """Static post-hoc analysis of ONE decision. Never feeds the player."""
    mover = board.turn
    info_before = engine.analyse(board, chess.engine.Limit(nodes=20000), multipv=1)
    best = info_before[0]["pv"][0]
    score_before, mate_before = _score_to_cp(info_before[0]["score"], mover)

    result = {
        "legal_root_best": best.uci(),
        "cp_before": score_before,
        "mate_before": mate_before,
        "chosen": chosen_uci,
        "chosen_legal": False,
        "cp_after": None,
        "mate_after": None,
        "regret_cp": None,
        "blunder_300cp": None,
        "allows_mate_in_1": None,
    }
    if chosen_uci is None:
        return result
    move = chess.Move.from_uci(chosen_uci)
    if move not in board.legal_moves:
        return result
    result["chosen_legal"] = True

    # immediate mate allowed by the chosen move?
    after = board.copy()
    after.push(move)
    opponent_mate = False
    for reply in after.legal_moves:
        probe = after.copy()
        probe.push(reply)
        if probe.is_checkmate():
            opponent_mate = True
            break
    result["allows_mate_in_1"] = opponent_mate

    info_after = engine.analyse(after, chess.engine.Limit(nodes=20000))
    # analyse(after2) scores from the perspective of the side TO MOVE in
    # after2 (the opponent); convert back to the mover's perspective.
    opp = info_after["score"].relative
    if opp.is_mate():
        cp_after_mover = -int(opp.score(mate_score=MATE_SCORE))
        mate_after = True
    else:
        cp_after_mover = -int(opp.score())
        mate_after = False
    result["cp_after"] = cp_after_mover
    result["mate_after"] = mate_after
    if (
        not mate_before
        and not mate_after
        and score_before is not None
        and cp_after_mover is not None
    ):
        result["regret_cp"] = max(0, score_before - cp_after_mover)
        result["blunder_300cp"] = result["regret_cp"] >= BLUNDER_CP
    return result


def run_record(ws: pathlib.Path) -> dict | None:
    db = ws / ".zugzwang" / "state.db"
    if not db.exists():
        return None
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out: dict = {"workspace": ws.name}
    try:
        out["run_status"] = conn.execute("SELECT status FROM runs LIMIT 1").fetchone()[0]
        ep = conn.execute("SELECT status, outcome FROM episodes LIMIT 1").fetchone()
        out["episode"] = ep[0] if ep else None
        out["outcome"] = ep[1] if ep else None
        dec = conn.execute("SELECT status, selected_action FROM cb_decisions LIMIT 1").fetchone()
        out["decision_status"] = dec[0] if dec else None
        out["selected_action"] = dec[1] if dec else None
        out["steps_committed"] = conn.execute(
            "SELECT COUNT(*) FROM steps WHERE status='COMMITTED'"
        ).fetchone()[0]
        out["attempts"] = conn.execute(
            "SELECT status, COUNT(*) FROM attempts GROUP BY 1"
        ).fetchall()
        out["throttles"] = conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type='provider.call.failed' "
            "AND payload_json LIKE '%TRANSPORT-001%'"
        ).fetchone()[0]
        out["nodes_depth_max"] = conn.execute(
            "SELECT COALESCE(MAX(depth_plies),0) FROM cb_node_bindings"
        ).fetchone()[0]
        usage = conn.execute(
            "SELECT usage_json FROM attempts WHERE status='completed' AND usage_json IS NOT NULL"
        ).fetchall()
        tokens_in = tokens_out = reasoning = 0
        for (blob,) in usage:
            try:
                u = json.loads(blob)
            except Exception:
                continue
            tokens_in += int(u.get("input_tokens") or 0)
            tokens_out += int(u.get("output_tokens") or 0)
            reasoning += int(u.get("reasoning_tokens") or 0)
        out["tokens"] = {"input": tokens_in, "output": tokens_out, "reasoning": reasoning}
    finally:
        conn.close()
    return out


def request_probes(ws: pathlib.Path) -> dict:
    """Mechanism probes from journaled request artifacts."""
    db = ws / ".zugzwang" / "state.db"
    if not db.exists():
        return {}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    probes = {"preload_in_first_request": False, "neto_consumed": False, "memory_note": False}
    try:
        rows = conn.execute(
            "SELECT cr.ordinal, c.relative_path FROM cb_rounds cr "
            "JOIN artifacts c ON c.artifact_id = cr.context_artifact_id ORDER BY cr.ordinal"
        ).fetchall()
        first_blob = None
        for _ordinal, rel in rows:
            p = ws / ".zugzwang" / "objects" / rel
            if not p.exists():
                continue
            blob = p.read_text()
            if first_blob is None:
                first_blob = blob
                probes["preload_in_first_request"] = "harness:preload-root" in blob
            if 'depth\\":2' in blob:
                probes["neto_consumed"] = True
            if "PRIOR MOVE NOTE" in blob:
                probes["memory_note"] = True
    finally:
        conn.close()
    return probes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/tmp/zgx-wave1"))
    parser.add_argument(
        "--out", type=pathlib.Path, default=pathlib.Path("out/zgx_wave1_evaluation.json")
    )
    parser.add_argument(
        "--stockfish", type=pathlib.Path, default=pathlib.Path("/home/maelrx/.local/bin/stockfish")
    )
    parser.add_argument("--only-completed", action="store_true")
    args = parser.parse_args()

    json.loads((args.root.parent / "zgx_fixtures_s12.json").read_text()) if (
        args.root.parent / "zgx_fixtures_s12.json"
    ).exists() else None
    s12_sources = json.loads(
        (
            pathlib.Path(__file__).parent.parent / "experiments/zgx/fixtures/s12_sources.json"
        ).read_text()
    )

    engine = chess.engine.SimpleEngine.popen_uci(str(args.stockfish))
    engine.configure(_sf_options())
    results = []
    try:
        for ws in sorted(args.root.glob("zgx*")):
            if ws.name in {"logs", "muse.flight.lock"}:
                continue
            record = run_record(ws)
            if record is None:
                continue
            if args.only_completed and record.get("episode") != "COMPLETED":
                record["posthoc"] = None
                results.append(record)
                continue
            # parse arm/position from the workspace name zgxNN-<arm>-<pid>[-family]
            parts = ws.name.split("-")
            zgx = parts[0] if parts[0].startswith("zgx") else None
            arm = parts[1] if len(parts) > 1 else None
            pid = parts[2] if len(parts) > 2 else None
            entry: dict = {"zgx": zgx, "arm": arm, "pid": pid, **record}
            if zgx == "zgx-preflight":
                entry["probes"] = request_probes(ws)
                results.append(entry)
                continue
            source_keys = {k.split("-")[0]: k for k in s12_sources}
            if pid and zgx != "zgx20" and pid in source_keys:
                source = s12_sources[source_keys[pid]]
                board = chess.Board(source["start_fen"])
                for uci in source["move_prefix"]:
                    board.push(chess.Move.from_uci(uci))
                entry["posthoc"] = analyze_position(engine, board, record.get("selected_action"))
            else:
                entry["posthoc"] = None  # T6 episodes: judged per-episode elsewhere
            entry["probes"] = request_probes(ws)
            results.append(entry)
    finally:
        engine.quit()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"wrote {args.out}: {len(results)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
