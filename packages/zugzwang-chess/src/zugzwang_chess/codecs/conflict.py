"""Deterministic one-piece conflict transform for MM-002 (FR-066).

Displaces exactly one minor piece to an empty square, changing the rendered
board while the symbolic state stays untouched. Pure function of the FEN.
"""

from __future__ import annotations


def displace_one_minor_piece(fen: str) -> str:
    """Return a FEN with one minor piece moved to the nearest empty square."""
    board_part, *rest = fen.split(" ")
    rows = board_part.split("/")
    target = None
    for piece_set in ("NnBb", "RrQq", "Pp"):
        for row_index, row in enumerate(rows):
            for col_index, char in enumerate(row):
                if char in piece_set:
                    target = (row_index, col_index, char)
                    break
            if target:
                break
        if target:
            break
    if target is None:
        raise ValueError(f"no piece to displace in {fen!r}")
    row_index, col_index, char = target
    rows[row_index] = rows[row_index][:col_index] + "1" + rows[row_index][col_index + 1 :]
    dest_row = rows[(row_index + 2) % 8]
    dest_chars = list(dest_row)
    digit_index = next((i for i, c in enumerate(dest_chars) if c.isdigit()), None)
    if digit_index is None:
        raise ValueError("no empty square found for conflict displacement")
    dest_chars[digit_index] = str(int(dest_chars[digit_index]) - 1) + char
    rows[(row_index + 2) % 8] = "".join(dest_chars)
    return "/".join(rows) + " " + " ".join(rest)
