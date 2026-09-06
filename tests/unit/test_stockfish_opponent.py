from __future__ import annotations

import pytest
from zgw_eval_stockfish.opponent import StockfishOpponent


def test_stockfish_opponent_rejects_elo_below_engine_floor() -> None:
    with pytest.raises(ValueError, match="allow_approximate=true"):
        StockfishOpponent("/tmp/does-not-exist/stockfish", elo=1000)


def test_stockfish_opponent_records_strength_and_limit() -> None:
    opponent = StockfishOpponent(
        "/tmp/does-not-exist/stockfish",
        elo=1500,
        limit={"nodes": 20_000},
        options={"Hash": "32"},
    )

    assert opponent.policy_id == "chess.stockfish-elo-1500"
    assert opponent.metadata["requested_elo"] == 1500
    assert opponent.metadata["requested_uci_elo"] == 1500
    assert opponent.metadata["effective_uci_elo"] == 1500
    assert opponent.metadata["strength_mode"] == "native_uci_elo"
    assert opponent.metadata["limit"] == {"nodes": 20_000}
    assert opponent.metadata["options"]["UCI_LimitStrength"] == "true"
    assert opponent.metadata["options"]["UCI_Elo"] == "1500"
    assert opponent.metadata["options"]["Hash"] == "32"


def test_stockfish_opponent_can_run_a_below_floor_bucket_explicitly() -> None:
    opponent = StockfishOpponent(
        "/tmp/does-not-exist/stockfish",
        elo=1000,
        allow_approximate=True,
    )

    assert opponent.policy_id == "chess.stockfish-elo-1000"
    assert opponent.metadata["requested_elo"] == 1000
    assert opponent.metadata["requested_uci_elo"] is None
    assert opponent.metadata["effective_uci_elo"] == 1320
    assert opponent.metadata["strength_mode"] == "approximate_skill_floor"
    assert opponent.metadata["options"]["UCI_Elo"] == "1320"
    assert opponent.metadata["options"]["Skill Level"] == "0"


def test_stockfish_opponent_requires_engine_limit_kind() -> None:
    with pytest.raises(ValueError, match="depth, nodes or movetime"):
        StockfishOpponent("/tmp/does-not-exist/stockfish", elo=1500, limit={"threads": 1})
