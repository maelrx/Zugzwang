"""Explicit Stockfish opponent policy for live, non-assisting games.

The engine is a separate player, not a tool exposed to the model. Strength is
configured through UCI_LimitStrength/UCI_Elo and every move carries the policy
metadata needed to distinguish the opponent from post-hoc evaluation.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from zugzwang_chess.environment.standard import ChessGameState, ChessMove

from .uci import EngineLimit, UciEngineClient


class StockfishOpponent:
    """Choose legal moves with an external Stockfish UCI process."""

    policy_id = "chess.stockfish"
    version = "0.1.0"
    min_requested_elo = 1000
    min_uci_elo = 1320
    max_uci_elo = 3190

    def __init__(
        self,
        executable: str = "stockfish",
        *,
        elo: int | None = None,
        limit: EngineLimit | None = None,
        options: dict[str, str] | None = None,
        allow_approximate: bool = False,
    ) -> None:
        if elo is not None and not self.min_requested_elo <= elo <= self.max_uci_elo:
            raise ValueError(
                f"Stockfish requested Elo must be between {self.min_requested_elo} "
                f"and {self.max_uci_elo}; requested {elo}"
            )
        if elo is not None and elo < self.min_uci_elo and not allow_approximate:
            raise ValueError(
                f"Stockfish UCI_Elo must be between {self.min_uci_elo} "
                f"and {self.max_uci_elo}; requested {elo}; "
                "set allow_approximate=true for the below-floor skill profile"
            )
        if not limit:
            limit = {"nodes": 20_000}
        if any(value <= 0 for value in limit.values()):
            raise ValueError("Stockfish engine limits must contain positive integers")
        if not any(key in {"depth", "nodes", "movetime"} for key in limit):
            raise ValueError("Stockfish limit must include depth, nodes or movetime")

        self._executable = shutil.which(executable) or executable
        self._elo = elo
        self._allow_approximate = allow_approximate
        self._approximate = elo is not None and elo < self.min_uci_elo
        self._effective_uci_elo = max(elo, self.min_uci_elo) if elo is not None else None
        self._limit = dict(limit)
        self._options = {"Threads": "1", "Hash": "16", **(options or {})}
        if elo is not None:
            self._options.update(
                {
                    "UCI_LimitStrength": "true",
                    "UCI_Elo": str(self._effective_uci_elo),
                }
            )
            if self._approximate:
                self._options["Skill Level"] = "0"
        self._binary_sha256 = self._hash_binary(executable)
        self._engine_name = ""
        self._engine_author = ""
        self.policy_id = f"chess.stockfish-elo-{elo}" if elo is not None else self.policy_id

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "executable": self._executable,
            "binary_sha256": self._binary_sha256,
            "requested_elo": self._elo,
            "requested_uci_elo": self._elo if not self._approximate else None,
            "effective_uci_elo": self._effective_uci_elo,
            "strength_mode": (
                "approximate_skill_floor"
                if self._approximate
                else "native_uci_elo"
                if self._elo is not None
                else "engine_default"
            ),
            "approximate": self._approximate,
            "allow_approximate": self._allow_approximate,
            "limit": dict(self._limit),
            "options": dict(self._options),
            "engine_name": self._engine_name,
            "engine_author": self._engine_author,
        }

    async def choose(
        self, state: ChessGameState, legal_actions: tuple[ChessMove, ...], seed: int
    ) -> ChessMove:
        if not legal_actions:
            raise ValueError("no legal actions available")
        engine = UciEngineClient(self._executable, options=self._options)
        try:
            info = await engine.start()
            self._engine_name = info.name
            self._engine_author = info.author
            await engine.position(state.fen)
            analysis = await engine.go(self._limit)
            if not analysis.bestmove:
                raise ValueError("Stockfish returned no bestmove")
            action = ChessMove(analysis.bestmove)
            if action not in legal_actions:
                raise ValueError(f"Stockfish returned illegal move {analysis.bestmove!r}")
            return action
        finally:
            await engine.quit()

    @staticmethod
    def _hash_binary(executable: str) -> str:
        try:
            resolved = shutil.which(executable) or executable
            return hashlib.sha256(Path(resolved).read_bytes()).hexdigest()
        except OSError:
            return ""
