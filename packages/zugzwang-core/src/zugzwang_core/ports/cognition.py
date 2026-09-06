"""CognitiveBoard ports (PRD §11.1, §26.1): identity and decision session.

Protocols only — the core never imports chess, runtime or providers. A
factory in the runtime creates the concrete session; strategies receive it
through the optional ``DecisionContext.decision_session`` field.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..domain.cognition import ToolEnvelope


@runtime_checkable
class StateIdentityPort(Protocol):
    """Canonical identity projection of integral state (PRD §7.2/§7.4).

    Implementations produce the distinct §7.2 keys over the effective rules
    context; two states that share ``position_key_v2`` may still differ in
    counters and history, so position equivalence never authorizes reusing
    termination, draw claims or historical evaluation without context.
    """

    def state_key(self, state: Any) -> str:
        """Integral normalized state + variant + rules context (state_key_v2)."""
        ...

    def position_key(self, state: Any) -> str:
        """Equivalent-position projection (position_key_v2)."""
        ...

    def action_key(self, state: Any, uci: str, policy_hash: str) -> str:
        """State-bound action identity (action_id_v2)."""
        ...


@runtime_checkable
class CognitiveSession(Protocol):
    """Authorized decision-scoped operations (PRD §11.1 surface).

    Each operation returns a normalized ``ToolEnvelope``; the session owns
    scoping, budgets and audit — never a database or filesystem handle.
    """

    def board_observe(self, arguments: dict[str, Any]) -> ToolEnvelope:
        """Deterministic L0 views of the current position."""
        ...

    def board_inspect(self, arguments: dict[str, Any]) -> ToolEnvelope:
        """Inspect one element of the current views without advancing."""
        ...

    def board_expand(self, arguments: dict[str, Any]) -> ToolEnvelope:
        """Expand a node with candidate actions (no legality invention)."""
        ...

    def board_compare(self, arguments: dict[str, Any]) -> ToolEnvelope:
        """Compare nodes/positions within the decision scope."""
        ...

    def memory_recall(self, arguments: dict[str, Any]) -> ToolEnvelope:
        """Recall decision-scoped memory under the eligibility policy."""
        ...

    def analysis_record(self, arguments: dict[str, Any]) -> ToolEnvelope:
        """Record model analysis into the decision transcript."""
        ...
