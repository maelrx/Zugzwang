from __future__ import annotations

from zugzwang.evaluation.move_quality import classify_centipawn_loss


def test_classify_centipawn_loss_boundaries() -> None:
    assert classify_centipawn_loss(0) == "best"
    assert classify_centipawn_loss(10) == "excellent"
    assert classify_centipawn_loss(30) == "good"
    assert classify_centipawn_loss(100) == "inaccuracy"
    assert classify_centipawn_loss(200) == "mistake"
    assert classify_centipawn_loss(201) == "blunder"
