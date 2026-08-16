"""Opponents package: random legal, scripted, and (M4) UCI engine."""

from .random_legal import Opponent, RandomLegalOpponent, ScriptedOpponent

__all__ = ["Opponent", "RandomLegalOpponent", "ScriptedOpponent"]
