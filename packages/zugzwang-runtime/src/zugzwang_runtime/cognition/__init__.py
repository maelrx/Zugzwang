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
    "DecisionSession",
    "ToolExecutionError",
    "ToolOperationBudget",
    "cas_artifact_loader",
    "cas_artifact_sink",
    "identity_keys",
]
