from __future__ import annotations


def unicode_board_from_fen(fen: str) -> str:
    board_part = fen.split(" ", 1)[0]
    rows = board_part.split("/")
    expanded: list[str] = []
    for row in rows:
        row_cells: list[str] = []
        for token in row:
            if token.isdigit():
                row_cells.extend(["."] * int(token))
            else:
                row_cells.append(token)
        expanded.append(" ".join(row_cells))
    return "\n".join(expanded)


def board_context_lines(fen: str, board_format: str, pgn: str | None = None) -> list[str]:
    format_key = str(board_format or "fen").lower()
    if format_key == "fen":
        return [f"FEN: {fen}"]
    if format_key == "pgn":
        parsed_pgn = (pgn or "").strip()
        if parsed_pgn:
            return [f"PGN: {parsed_pgn}"]
        return [
            "PGN: (not available yet)",
            f"FEN: {fen}",
        ]
    if format_key in {"ascii", "unicode"}:
        return [f"Board (unicode):\n{unicode_board_from_fen(fen)}"]
    if format_key == "combined":
        return [
            f"FEN: {fen}",
            f"Board (unicode):\n{unicode_board_from_fen(fen)}",
        ]
    return [f"FEN: {fen}"]
