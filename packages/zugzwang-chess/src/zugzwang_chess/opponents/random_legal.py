"""Opponents for full games (design §14.7).

Random legal is a protocol baseline, not a strength baseline.
"""

from __future__ import annotations

import random
from typing import Protocol, runtime_checkable

from ..environment.standard import ChessGameState, ChessMove


@runtime_checkable
class Opponent(Protocol):
    """A policy that chooses a move for a side (no provider calls)."""

    async def choose(
        self, state: ChessGameState, legal_actions: tuple[ChessMove, ...], seed: int
    ) -> ChessMove: ...


class RandomLegalOpponent:
    """Seeded random legal mover."""

    policy_id = "chess.random-legal"
    version = "0.1.0"

    async def choose(
        self, state: ChessGameState, legal_actions: tuple[ChessMove, ...], seed: int
    ) -> ChessMove:
        rng = random.Random(seed)
        if not legal_actions:
            raise ValueError("no legal actions available")
        return rng.choice(legal_actions)


class ScriptedOpponent:
    """Replays a fixed UCI script; fails closed when the script runs out."""

    policy_id = "chess.scripted"
    version = "0.1.0"

    def __init__(self, script: tuple[str, ...]) -> None:
        self._script = list(script)
        self._index = 0

    async def choose(
        self, state: ChessGameState, legal_actions: tuple[ChessMove, ...], seed: int
    ) -> ChessMove:
        if self._index >= len(self._script):
            raise ValueError("scripted opponent ran out of moves")
        uci = self._script[self._index]
        self._index += 1
        move = ChessMove(uci)
        if move not in legal_actions:
            raise ValueError(f"scripted move {uci!r} is not legal here")
        return move
