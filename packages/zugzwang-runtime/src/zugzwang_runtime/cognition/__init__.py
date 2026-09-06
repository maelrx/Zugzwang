"""CognitiveBoard cognition package (PRD §11, §26.1; CB-WO-05).

The broker is the single authorized door to the L0 tools; the session
factory composes journal + perception + broker for one decision.
"""

from .audit import AuditReport, audit_decision, export_report, redact, validate_artifact_id
from .broker import (
    TOOL_CATALOG,
    ArtifactLoader,
    ArtifactSink,
    CognitionToolBroker,
    ToolExecutionError,
    ToolOperationBudget,
)
from .loop import CognitiveLoop, LoopResult, LoopStep, count_protocol_errors, is_retryable
from .memory import MemoryError, RecalledItem, RecallResult, ScopedMemoryStore
from .resume import ResumePlan, open_operations, resume_decision
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
    "AuditReport",
    "CognitionToolBroker",
    "CognitiveLoop",
    "DecisionSession",
    "LoopResult",
    "LoopStep",
    "MemoryError",
    "RecallResult",
    "RecalledItem",
    "ResumePlan",
    "ScopedMemoryStore",
    "ToolExecutionError",
    "ToolOperationBudget",
    "audit_decision",
    "cas_artifact_loader",
    "cas_artifact_sink",
    "count_protocol_errors",
    "export_report",
    "identity_keys",
    "is_retryable",
    "open_operations",
    "redact",
    "resume_decision",
    "validate_artifact_id",
]
