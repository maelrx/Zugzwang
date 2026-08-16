"""Stockfish evaluator plugin entry point."""

from __future__ import annotations

from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

from .evaluator import StockfishEvaluator
from .uci import FakeUciEngine, UciEngineClient

__version__ = "0.1.0.dev0"
__all__ = ["FakeUciEngine", "StockfishEvaluator", "UciEngineClient", "plugin"]


class _Plugin:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="evaluator.stockfish",
            plugin_version=__version__,
            kind=PluginKind.EVALUATOR,
            capabilities=("chess.cp_eval", "chess.multipv", "chess.mate"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


plugin = _Plugin()
