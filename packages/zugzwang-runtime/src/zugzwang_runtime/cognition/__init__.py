"""CognitiveBoard cognition package (PRD §11, §26.1; CB-WO-05).

The broker is the single authorized door to the L0 tools; the session
factory composes journal + perception + broker for one decision.
"""

from .broker import (
    TOOL_CATALOG,
    ArtifactLoader,
    ArtifactSink,
    CognitionToolBroker,
    ToolExecutionError,
    ToolOperationBudget,
)
from .loop import CognitiveLoop, LoopResult, LoopStep, count_protocol_errors, is_retryable
from .session import (
    DecisionSession,
    cas_artifact_loader,
    cas_artifact_sink,
    identity_keys,
)

__all__ = [
    "TOOL_CATALOG",
    "ArtifactLoader",
    "ArtifactSink",
    "CognitionToolBroker",
    "CognitiveLoop",
    "DecisionSession",
    "LoopResult",
    "LoopStep",
    "ToolExecutionError",
    "ToolOperationBudget",
    "cas_artifact_loader",
    "cas_artifact_sink",
    "count_protocol_errors",
    "identity_keys",
    "is_retryable",
]
