"""CognitiveBoard L0 perception (PRD §8, CB-WO-03).

Deterministic facts about chess positions: PositionPacket, formal relations
and PositionDelta. No evaluation, ranking, pruning or strategic judgment —
those live above the L0 contract (ADR-CB-002).
"""

from .delta import PieceChange, PositionDelta, compute_delta, reconstruct
from .packet import (
    ActionStateMismatch,
    LegalActionItem,
    PacketLegalActions,
    PacketProvenance,
    PacketRelations,
    PacketRepresentation,
    PacketState,
    PacketTerminal,
    PositionPacket,
    position_keys,
    require_action_belongs,
)
from .perception import PERCEPTION_VERSION, ChessPerception

__all__ = [
    "PERCEPTION_VERSION",
    "ActionStateMismatch",
    "ChessPerception",
    "LegalActionItem",
    "PacketLegalActions",
    "PacketProvenance",
    "PacketRelations",
    "PacketRepresentation",
    "PacketState",
    "PacketTerminal",
    "PieceChange",
    "PositionDelta",
    "PositionPacket",
    "compute_delta",
    "position_keys",
    "reconstruct",
    "require_action_belongs",
]
