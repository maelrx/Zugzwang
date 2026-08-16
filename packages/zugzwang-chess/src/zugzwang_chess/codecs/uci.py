"""UCI codec: the canonical persisted action identity (ADR-023).

UCI is unambiguous, trivially parseable and free of ``+/#`` markers. SAN is
an interface codec only.
"""

from __future__ import annotations

import re

from zugzwang_core.domain.errors import OutputParseError

from ..environment.standard import ChessMove

_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def parse_uci(value: str, *, raise_on_invalid: bool = True) -> ChessMove | None:
    """Parse a canonical UCI string like ``e2e4`` or ``e7e8q``.

    Returns ``None`` (or raises OutputParseError) for malformed input. This is
    parsing only — legality is verified separately against the environment.
    """
    text = value.strip()
    if not _UCI_RE.fullmatch(text):
        if raise_on_invalid:
            raise OutputParseError(
                f"invalid UCI move {value!r}",
                technical_context="expected format like e2e4 or e7e8q",
            )
        return None
    return ChessMove(text)


def format_uci(move: ChessMove) -> str:
    return move.uci
