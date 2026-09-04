"""Capability-scoped formal legality gateway.

``RulesKernel`` can enumerate everything internally.  This gateway is the only
object a strategy receives and decides which subset is visible in a phase.
Every query is budgeted and evented; no query evaluates strategic quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zugzwang_core.domain.assistance import AssistanceImpact, HClass, KClass
from zugzwang_core.domain.errors import BudgetExceededError, CapabilityError
from zugzwang_core.domain.events import EventAssistance, EventContext, EventEnvelope
from zugzwang_core.ports.rules import (
    DecisionCapabilities,
    LegalityGatewayConfig,
    LegalityResult,
    RulesKernel,
)

from .event_sink import EventSink


@dataclass(slots=True)
class GatewayStats:
    validation_queries: int = 0
    transition_queries: int = 0
    terminal_queries: int = 0
    enumeration_queries: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "validation_queries": self.validation_queries,
            "transition_queries": self.transition_queries,
            "terminal_queries": self.terminal_queries,
            "enumeration_queries": self.enumeration_queries,
        }


@dataclass(slots=True)
class LegalityGateway:
    """Factory for phase-bound gateways over one trusted rules kernel."""

    kernel: RulesKernel
    config: LegalityGatewayConfig = field(default_factory=LegalityGatewayConfig)
    event_sink: EventSink | None = None
    stats: GatewayStats = field(default_factory=GatewayStats)

    def bind(
        self,
        *,
        state: Any,
        capabilities: DecisionCapabilities,
        context: EventContext | None = None,
    ) -> BoundLegalityGateway:
        return BoundLegalityGateway(
            kernel=self.kernel,
            config=self.config,
            state=state,
            capabilities=capabilities,
            event_sink=self.event_sink,
            stats=self.stats,
            context=context,
        )


@dataclass(slots=True)
class BoundLegalityGateway:
    """A lease-bound view of formal truth for one immutable state."""

    kernel: RulesKernel
    config: LegalityGatewayConfig
    state: Any
    capabilities: DecisionCapabilities
    event_sink: EventSink | None = None
    stats: GatewayStats = field(default_factory=GatewayStats)
    context: EventContext | None = None

    def bind_state(
        self,
        state: Any,
        *,
        context: EventContext | None = None,
    ) -> BoundLegalityGateway:
        """Bind the same lease to a hypothetical SearchWorkspace state."""
        return BoundLegalityGateway(
            kernel=self.kernel,
            config=self.config,
            state=state,
            capabilities=self.capabilities,
            event_sink=self.event_sink,
            stats=self.stats,
            context=context or self.context,
        )

    def validate(self, action: Any) -> LegalityResult:
        self._require(self.capabilities.validate_action, "validate_action")
        self._limit("validations", self.stats.validation_queries)
        self.stats.validation_queries += 1
        self._emit("gateway.validation.requested", {"action": str(action)})
        canonical_action = action
        if isinstance(action, str):
            parsed = self.kernel.parse_action(action, "canonical")
            if not parsed.valid or parsed.parsed is None:
                result = LegalityResult(
                    legal=False,
                    action=action,
                    reason="ILLEGAL_PARSE",
                )
            else:
                canonical_action = parsed.parsed
                result = self.kernel.is_legal(self.state, canonical_action)
        else:
            result = self.kernel.is_legal(self.state, canonical_action)
        self._emit(
            "gateway.validation.completed",
            {"action": str(action), "legal": result.legal, "reason": result.reason},
            assistance_h=HClass.H1,
        )
        return result

    def model_feedback(self, result: LegalityResult) -> dict[str, Any]:
        """Project a validation result according to the current lease."""
        mode = self.capabilities.validation_feedback
        if mode == "none":
            return {}
        if mode == "reason_category":
            return {"legal": bool(result.legal), "reason": result.reason}
        # Binary is deliberately only one bit.  In particular, no count or
        # legal-action list is included here.
        return {"legal": bool(result.legal)}

    def enumerate_actions(self) -> Any:
        self._require(self.capabilities.enumerate_actions, "enumerate_actions")
        self._limit("validations", self.stats.enumeration_queries)
        self.stats.enumeration_queries += 1
        self._emit("gateway.enumeration.requested", {})
        result = self.kernel.legal_actions(self.state)
        self._emit(
            "gateway.enumeration.completed",
            {"count": len(result.actions), "legal_hash": result.legal_hash},
            assistance_h=HClass.H3,
        )
        return result

    def try_move(self, action: Any) -> Any:
        self._require(self.capabilities.transition_sandbox, "transition_sandbox")
        self._limit("transitions", self.stats.transition_queries)
        self.stats.transition_queries += 1
        result = self.validate(action)
        if not result.legal:
            return {
                "legal": False,
                "reason": result.reason,
                "child_state_ref": None,
                "terminal": False,
            }
        self._emit("gateway.transition.requested", {"action": str(action)})
        transition = self.kernel.transition(self.state, action)
        self._emit(
            "gateway.transition.completed",
            {
                "action": str(action),
                "terminal": bool(transition.terminal),
                "state_fingerprint": _fingerprint(transition.state),
            },
            assistance_h=HClass.H2,
        )
        return {
            "legal": True,
            "child_state": transition.state,
            "child_state_ref": _fingerprint(transition.state),
            "terminal": bool(transition.terminal),
            "termination": (
                transition.termination.model_dump(mode="json")
                if transition.termination is not None
                else None
            ),
        }

    def validate_line(self, actions: list[Any] | tuple[Any, ...]) -> dict[str, Any]:
        self._require(self.capabilities.transition_sandbox, "transition_sandbox")
        if len(actions) > self.config.limits.depth_plies:
            raise BudgetExceededError(
                "line exceeds legality gateway depth budget",
                technical_context=f"depth={len(actions)} limit={self.config.limits.depth_plies}",
            )
        current = self.state
        results: list[dict[str, Any]] = []
        for action in actions:
            self.stats.transition_queries += 1
            self._limit("transitions", self.stats.transition_queries)
            legality = self.kernel.is_legal(current, action)
            item: dict[str, Any] = {"action": str(action), "legal": bool(legality.legal)}
            if not legality.legal:
                item["reason"] = legality.reason
                results.append(item)
                break
            transition = self.kernel.transition(current, action)
            current = transition.state
            item["terminal"] = bool(transition.terminal)
            item["state_fingerprint"] = _fingerprint(current)
            results.append(item)
            if transition.terminal:
                break
        return {"legal": all(bool(item["legal"]) for item in results), "steps": results}

    def terminal(self) -> Any:
        self._require(self.capabilities.query_terminal, "query_terminal")
        self._limit("transitions", self.stats.terminal_queries)
        self.stats.terminal_queries += 1
        return self.kernel.terminal(self.state)

    def assistance_impacts(self) -> tuple[AssistanceImpact, ...]:
        impacts: list[AssistanceImpact] = []
        if self.stats.validation_queries:
            impacts.append(AssistanceImpact(h=HClass.H1, k=KClass.K0, source="binary_legality"))
        if self.stats.enumeration_queries:
            impacts.append(AssistanceImpact(h=HClass.H3, k=KClass.K0, source="legal_action_set"))
        if self.stats.transition_queries:
            impacts.append(AssistanceImpact(h=HClass.H2, k=KClass.K0, source="transition_sandbox"))
        return tuple(impacts)

    def _require(self, allowed: bool, capability: str) -> None:
        if not allowed:
            raise CapabilityError(
                f"legality capability {capability!r} is not leased for this phase"
            )

    def _limit(self, name: str, current: int) -> None:
        limits = self.config.limits
        limit = limits.validations if name == "validations" else limits.transitions
        if current >= limit:
            raise BudgetExceededError(
                f"legality gateway {name} budget exhausted",
                technical_context=f"used={current} limit={limit}",
            )

    def _emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        assistance_h: HClass | None = None,
    ) -> None:
        if self.event_sink is None or self.context is None:
            return
        self.event_sink.append(
            EventEnvelope.create(
                event_type=event_type,
                payload=payload,
                stream_type="step",
                stream_id=self.context.step_id or self.context.run_id,
                sequence=0,
                context=self.context,
                assistance=(
                    EventAssistance(h=assistance_h, k=KClass.K0, source="legality_gateway")
                    if assistance_h is not None
                    else None
                ),
            )
        )


def _fingerprint(state: Any) -> str | None:
    value = getattr(state, "fingerprint", None)
    return str(value()) if callable(value) else (str(value) if value else None)
