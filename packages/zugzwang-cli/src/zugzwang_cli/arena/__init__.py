"""Arena play mode (ZGW-0108): interactive human-vs-model games.

Local-only, non-canonical sessions. Every provider call is recorded verbatim
(``calls.jsonl``) even though no run bundle is produced — attribution applies
per call, not per run. The wire protocol mirrors ``chess.cognitive_navigation``
native_tools so campaign behavior carries over, while legality and state stay
server-side behind the real rules kernel.
"""

from .game import ArenaGame, MoveRecord
from .loop import ArenaDecisionLoop, DecisionOutcome, ModelCallInfo
from .positions import BoardFacade

__all__ = [
    "ArenaDecisionLoop",
    "ArenaGame",
    "BoardFacade",
    "DecisionOutcome",
    "ModelCallInfo",
    "MoveRecord",
]
