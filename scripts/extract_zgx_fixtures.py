#!/usr/bin/env python3
"""Extract REAL corpus positions (FEN + full move prefix) into the ZGX fixture
source file. Reads the arena workspace DBs (read-only) and the two dossier
J37/resume8 anchors; output is the frozen development fixture set for wave 1.

S12 = 6 families x 2 (plano 28 §4): captura boa (D7/G14 — engine-preferred
captures the model did not play), captura ruim (K4/L10 — unverified
sacrifices), urgência do rei (H21/I20), linha descoberta/peça em risco
(K9/L7), quieto construtivo com sucesso (resume8@14/J@30), final/conversão
(J37/resume8@20 — inclui um caso de mate em 1 executado com sucesso).
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

import chess

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

CASE_FENS = {
    "r1bqk1nr/pppn1pp1/4p2p/3p4/3P1b2/2N1PN2/PPP1BPPP/R2QK2R w KQkq - 0 7": "D7",
    "r1bq1rk1/pp3pp1/2np1n1p/2b1p3/2NpP3/2PB1N2/PP1B1PPP/R2QR1K1 w - - 0 12": "G14",
    "r1bqkbnr/ppp2ppp/2np4/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4": "K4",
    "1rbqkbnr/3n1ppp/p2p4/1p1B4/3BP3/8/PPP2PPP/RN1Q1RK1 w k - 2 10": "L10",
    "5knr/p3pp1p/6p1/7q/1n4N1/1Q1p1BP1/PP1PKP2/R1B5 w - - 0 21": "H21",
    "r3kbr1/ppp4p/2q5/8/2PP4/8/PP2bPPP/R4RK1 w q - 1 20": "I20",
    "r2qkbnr/ppp3pp/2np4/7b/3pP3/2N2N1P/PPP2PP1/R1BQ1RK1 w - - 1 9": "K9",
    "r1bqkbnr/1p1n1ppp/p2p4/2p5/2BNP3/4B3/PPP2PPP/RN1QK2R w KQkq - 0 7": "L7",
    "5rk1/R5p1/4K3/3P4/8/1P3P1p/P2Q1P1P/3R4 w - - 5 37": "J37",
}

WORKSPACES = [
    "/tmp/cb-arena-d",
    "/tmp/cb-arena-b",
    "/tmp/cb-arena-g",
    "/tmp/cb-arena-h",
    "/tmp/cb-arena-i",
    "/tmp/cb-arena-j",
    "/tmp/cb-arena-k",
    "/tmp/cb-arena-l",
    "/tmp/cb-pilot-resume8",
]


def states(ws: str):
    root = pathlib.Path(ws)
    db = root / ".zugzwang" / "state.db"
    if not db.exists():
        return
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for (rel,) in conn.execute(
        "SELECT a.relative_path FROM cb_state_snapshots s "
        "JOIN artifacts a ON a.artifact_id = s.state_artifact_id"
    ):
        p = root / ".zugzwang" / "objects" / rel
        if not p.exists():
            continue
        try:
            yield json.loads(p.read_text())
        except Exception:
            continue


def replay(prefix: list[str]) -> str:
    board = chess.Board()
    for uci in prefix:
        board.push(chess.Move.from_uci(uci))
    return board.fen()


def main() -> int:
    found: dict[str, dict] = {}
    for ws in WORKSPACES:
        for data in states(ws):
            fen = data.get("fen", "")
            case = CASE_FENS.get(fen)
            if case and case not in found and data.get("initial_fen") == START_FEN:
                found[case] = {
                    "move_prefix": list(data["move_stack"]),
                    "source": pathlib.Path(ws).name,
                }
    missing = sorted(set(CASE_FENS.values()) - set(found))
    if missing:
        print("MISSING corpus cases:", missing, file=sys.stderr)

    # resume8 mate success (20 plies, mate in 1 available and played)
    resume20 = None
    for data in states("/tmp/cb-pilot-resume8"):
        stack = data.get("move_stack") or []
        if len(stack) == 20 and data.get("initial_fen") == START_FEN:
            board = chess.Board(data["fen"])
            for mv in board.legal_moves:
                board.push(mv)
                if board.is_checkmate():
                    resume20 = {
                        "move_prefix": stack,
                        "source": "cb-pilot-resume8",
                        "gabarito_uci": mv.uci(),
                    }
                    break
                board.pop()
            if resume20:
                break
    if resume20 is None:
        print("MISSING resume8 mate position", file=sys.stderr)
        return 1

    found["J-conversion-early"] = None
    for data in states("/tmp/cb-arena-j"):
        stack = data.get("move_stack") or []
        if 30 <= len(stack) <= 60 and data.get("initial_fen") == START_FEN:
            board = chess.Board(data["fen"])
            vals = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
            score = sum(
                vals.get(p.piece_type, 0) * (1 if p.color == chess.WHITE else -1)
                for p in board.piece_map().values()
            )
            if score >= 5:
                found["J-conversion-early"] = {"move_prefix": stack, "source": "cb-arena-j@ply30"}
                break
    if found["J-conversion-early"] is None:
        print("MISSING J conversion position", file=sys.stderr)
        return 1

    entries = {
        # captura boa: engine-preferred captures the model declined (corpus)
        "p01-captura_boa": {"case": "D7", **found.get("D7", {})},
        "p02-captura_boa": {"case": "G14", **found.get("G14", {})},
        # captura ruim: unverified sacrifice actually played (corpus)
        "p03-captura_ruim": {"case": "K4", **found.get("K4", {})},
        "p04-captura_ruim": {"case": "L10", **found.get("L10", {})},
        # urgência do rei
        "p05-urgencia_rei": {"case": "H21", **found.get("H21", {})},
        "p06-urgencia_rei": {"case": "I20", **found.get("I20", {})},
        # linha descoberta / peça em risco
        "p07-linha_risco": {"case": "K9", **found.get("K9", {})},
        "p08-linha_risco": {"case": "L7", **found.get("L7", {})},
        # quieto construtivo com sucesso (corpus de vitória)
        "p09-quieto_sucesso": {
            "case": "resume8@ply14",
            "source": resume20["source"],
            "move_prefix": resume20["move_prefix"][:14],
        },
        "p10-quieto_sucesso": {"case": "J@ply30", **found["J-conversion-early"]},
        # final/conversão
        "p11-final_conversao": {"case": "J37", **found.get("J37", {})},
        "p12-final_conversao": {
            "case": "resume8@ply20",
            "source": resume20["source"],
            "move_prefix": resume20["move_prefix"],
        },
    }
    out = {}
    for pid, entry in entries.items():
        if "move_prefix" not in entry:
            print("INCOMPLETE:", pid, file=sys.stderr)
            continue
        prefix = entry["move_prefix"]
        out[pid] = {
            "case": entry["case"],
            "source": entry["source"],
            "start_fen": START_FEN,
            "move_prefix": prefix,
            "anchor_fen": replay(prefix),
        }
    dest = pathlib.Path("experiments/zgx/fixtures/s12_sources.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {dest}: {len(out)} positions")
    if len(out) != 12:
        print("INCOMPLETE SET", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
