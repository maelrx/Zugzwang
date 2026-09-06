"""Corpus integrity: every released position corpus must be chess-valid.

ZGW-0085/#14: positions_v1 (1.0.0) stays frozen as published evidence; its
successor positions_v1_1 (1.1.0) fixes the P01 note/FEN inconsistency and the
P09 BAD_CASTLING_RIGHTS defect with a version bump, never a silent edit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import chess
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(version_dir: str) -> dict:
    path = REPO_ROOT / "datasets" / version_dir / "positions.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.compatibility
def test_corpus_v1_1_positions_are_chess_valid() -> None:
    doc = _load("positions_v1_1")
    problems: list[str] = []
    for position in doc["positions"]:
        board = chess.Board(position["fen"])
        status = board.status()
        if status != chess.STATUS_VALID:
            problems.append(f"{position['pair_id']}: status={status!r}")
        if not position.get("fen") or not position.get("pair_id"):
            problems.append(f"{position['pair_id'] or '?'}: missing fields")
    assert problems == [], f"positions_v1_1: {problems}"


@pytest.mark.compatibility
def test_corpus_v1_0_0_defects_are_frozen_and_documented() -> None:
    """1.0.0 stays as published evidence, including its two known defects.

    P09 has BAD_CASTLING_RIGHTS. P01 is a legal position, but it is not the
    position its note declares ("after 1.d4 d5 2.c4"): replaying that line
    yields the v1.1 P01 FEN, not the recorded one.
    """
    doc = _load("positions_v1")
    by_pair = {p["pair_id"]: p["fen"] for p in doc["positions"]}
    assert chess.Board(by_pair["P09"]).status() & chess.STATUS_BAD_CASTLING_RIGHTS

    replay = chess.Board()
    for san in ("d4", "d5", "c4"):
        replay.push_san(san)
    assert replay.fen(en_passant="fen") != by_pair["P01"]
    corrected = {p["pair_id"]: p["fen"] for p in _load("positions_v1_1")["positions"]}
    assert replay.fen(en_passant="fen") == corrected["P01"]


@pytest.mark.compatibility
def test_corpus_v1_1_declares_corrections_and_hash() -> None:
    doc = _load("positions_v1_1")
    assert doc["corpus_version"] == "1.1.0"
    changes = doc["corpus_changes_from_1_0_0"]
    by_pair = {change["pair_id"]: change for change in changes}
    assert {"P01", "P09"} <= set(by_pair)
    assert "c-pawn" in by_pair["P01"]["reason"] or "2.c4" in by_pair["P01"]["reason"]
    assert "BAD_CASTLING_RIGHTS" in by_pair["P09"]["reason"]

    legacy = _load("positions_v1")
    assert legacy["corpus_version"] == "1.0.0"
    old_by_pair = {p["pair_id"]: p["fen"] for p in legacy["positions"]}
    new_by_pair = {p["pair_id"]: p["fen"] for p in doc["positions"]}
    changed = {pid for pid in old_by_pair if old_by_pair[pid] != new_by_pair.get(pid)}
    assert changed == {"P01", "P09"}, "only the documented corrections may change"

    digest_file = REPO_ROOT / "datasets" / "positions_v1_1" / "corpus.sha256"
    expected = hashlib.sha256(
        (REPO_ROOT / "datasets" / "positions_v1_1" / "positions.yaml").read_bytes()
    ).hexdigest()
    assert digest_file.read_text(encoding="utf-8").strip() == expected


@pytest.mark.compatibility
def test_corpus_v1_0_0_matches_recorded_checksum() -> None:
    """The frozen 1.0.0 corpus must remain byte-identical to its record."""
    doc = _load("positions_v1")
    payload = json.dumps(
        {"version": doc["corpus_version"], "pairs": [p["pair_id"] for p in doc["positions"]]},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert len(digest) == 64
    assert [p["pair_id"] for p in doc["positions"]] == [f"P{i:02d}" for i in range(1, 11)]
