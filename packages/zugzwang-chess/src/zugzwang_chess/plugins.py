"""Chess plugin entry definitions for registry discovery."""

from __future__ import annotations

from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel


class ChessEnvironmentDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.standard",
            plugin_version="0.1.0",
            kind=PluginKind.ENVIRONMENT,
            capabilities=("snapshot", "restore", "legal_actions", "uci", "fen"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessTaskDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.tasks",
            plugin_version="0.1.0",
            kind=PluginKind.TASK,
            capabilities=("move-selection", "full-game", "state-reconstruction"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessGroundedStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.grounded",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R1", "uci", "opaque_index"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessRepairStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.repair",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R2", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessStructuredStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.structured",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R3", "structured", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessReconstructStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.reconstruct",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R0", "fen"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessPolicyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.random-legal",
            plugin_version="0.1.0",
            kind=PluginKind.POLICY,
            capabilities=("random-legal",),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.direct",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R0", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


CHESS_ENVIRONMENT_ENTRY = ChessEnvironmentDefinition()
CHESS_TASK_ENTRY = ChessTaskDefinition()
CHESS_POLICY_ENTRY = ChessPolicyDefinition()
CHESS_STRATEGY_ENTRY = ChessStrategyDefinition()
CHESS_GROUNDED_STRATEGY_ENTRY = ChessGroundedStrategyDefinition()
CHESS_REPAIR_STRATEGY_ENTRY = ChessRepairStrategyDefinition()
CHESS_STRUCTURED_STRATEGY_ENTRY = ChessStructuredStrategyDefinition()
CHESS_RECONSTRUCT_STRATEGY_ENTRY = ChessReconstructStrategyDefinition()
