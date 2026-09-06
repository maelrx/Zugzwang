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


class ChessReasonThenGroundStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.reason_then_ground",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R1", "uci", "opaque_index", "san"),
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


class ChessBatchedTreeStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.r6_batched_tree",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R6", "model-only-search", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessMultiAgentReviewStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.multi_agent_review",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R5", "multi-agent-review", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessLegalTreeMemoryStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.legal_tree_memory",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R7", "legal-action-set", "model-search", "memory", "uci"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


class ChessSingleAgentTreeStrategyDefinition:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="chess.single_agent_tree",
            plugin_version="0.1.0",
            kind=PluginKind.STRATEGY,
            capabilities=(
                "R7",
                "single-agent",
                "legal-action-set",
                "model-search",
                "memory",
                "uci",
            ),
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
CHESS_REASON_THEN_GROUND_STRATEGY_ENTRY = ChessReasonThenGroundStrategyDefinition()
CHESS_REPAIR_STRATEGY_ENTRY = ChessRepairStrategyDefinition()
CHESS_STRUCTURED_STRATEGY_ENTRY = ChessStructuredStrategyDefinition()
CHESS_RECONSTRUCT_STRATEGY_ENTRY = ChessReconstructStrategyDefinition()
CHESS_R6_BATCHED_TREE_STRATEGY_ENTRY = ChessBatchedTreeStrategyDefinition()
CHESS_MULTI_AGENT_REVIEW_STRATEGY_ENTRY = ChessMultiAgentReviewStrategyDefinition()
CHESS_LEGAL_TREE_MEMORY_STRATEGY_ENTRY = ChessLegalTreeMemoryStrategyDefinition()
CHESS_SINGLE_AGENT_TREE_STRATEGY_ENTRY = ChessSingleAgentTreeStrategyDefinition()
