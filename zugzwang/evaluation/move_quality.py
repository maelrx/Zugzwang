from __future__ import annotations


def classify_centipawn_loss(cp_loss: int) -> str:
    if cp_loss <= 0:
        return "best"
    if cp_loss <= 10:
        return "excellent"
    if cp_loss <= 30:
        return "good"
    if cp_loss <= 100:
        return "inaccuracy"
    if cp_loss <= 200:
        return "mistake"
    return "blunder"
