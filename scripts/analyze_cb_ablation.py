"""Offline ablation analysis CB-01 (ZGW-0098): memory ON vs OFF, paired.

Deterministic, no network/engines: reads paired condition summaries
(position, seed, selection, ops charged, cost) and computes the preregistered
plan (docs/research/ABLATION_CB_01.md):

- TEST-071: evaluation metric in the side-to-move perspective; mate scores
  never enter a centipawn mean (counted separately);
- TEST-072: negative differences preserved and sign-flagged, no hidden abs;
- TEST-073: pairing requires identical positions/splits/versions/route;
  broken pairs are excluded and counted;
- TEST-074: precomputed formal work (journaled logical ops) enters the cost;
  monetary cost stays unknown (GATE-009).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_score(value: Any, perspective: str) -> dict[str, Any]:
    """Normalize one evaluation score to the side-to-move perspective.

    Mate scores ("#3", "-#2", "mate") never become centipawns: they are
    counted apart (TEST-071).
    """
    if isinstance(value, (int, float)):
        return {"cp": float(value), "mate": None, "perspective": perspective}
    text = str(value).strip()
    if text.startswith("#") or text.startswith("-#") or "mate" in text.lower():
        return {"cp": None, "mate": text, "perspective": perspective}
    try:
        return {"cp": float(text), "mate": None, "perspective": perspective}
    except ValueError:
        return {"cp": None, "mate": text, "perspective": perspective}


def mean_cp(scores: list[dict[str, Any]]) -> float | None:
    """Mean over centipawn scores only; None when all are mate (TEST-071)."""
    values = [score["cp"] for score in scores if score["cp"] is not None]
    if not values:
        return None
    return sum(values) / len(values)


def signed_delta(baseline: float, candidate: float) -> dict[str, Any]:
    """Difference with explicit sign preserved (TEST-072)."""
    delta = candidate - baseline
    return {"delta": delta, "sign": "+" if delta > 0 else ("-" if delta < 0 else "0")}


def pair_key(entry: dict[str, Any]) -> tuple[str, str, str, str, str] | None:
    """Pairing key: position/split/versions/route must match (TEST-073)."""
    try:
        return (
            str(entry["position"]),
            str(entry["split"]),
            str(entry["versions"]),
            str(entry["route"]),
            str(entry["seed"]),
        )
    except KeyError:
        return None


def analyze(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """Paired ON-vs-OFF analysis per the preregistered plan.

    Inputs must already be side-to-move perspective (TEST-071 documents,
    not converts: no hidden inversion). Broken pairs are excluded AND
    counted (TEST-073 dados completos).
    """
    matches = 0
    ops_deltas: list[dict[str, Any]] = []
    complete = 0
    excluded = 0
    for off, on in pairs:
        if pair_key(off) != pair_key(on) or pair_key(off) is None:
            excluded += 1
            continue
        complete += 1
        matches += 1 if off.get("selection") == on.get("selection") else 0
        ops_deltas.append(
            signed_delta(float(off.get("ops_charged", 0)), float(on.get("ops_charged", 0)))
        )
        # Formal precomputed work enters the cost (TEST-074); money unknown.
    return {
        "pairs_complete": complete,
        "pairs_excluded": excluded,
        "match_rate": (matches / complete) if complete else None,
        "ops_deltas": ops_deltas,
        "cost_money": "unknown",
        "cost_formal_ops": sum(delta["delta"] for delta in ops_deltas),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True, help="JSON list of [off, on]")
    parser.add_argument("--out", type=Path, required=True, help="report JSON output")
    args = parser.parse_args(argv)
    raw: Any = json.loads(args.pairs.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        parser.error("--pairs must be a JSON list of [off, on] pairs")
    entries: list[Any] = raw
    if any(not isinstance(entry, list) or len(entry) != 2 for entry in entries):
        parser.error("--pairs must be a JSON list of [off, on] pairs")
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = [(dict(a), dict(b)) for a, b in entries]
    report = analyze(pairs)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
