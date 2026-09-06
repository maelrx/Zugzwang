"""``chess.cognitive_navigation`` — the productive adaptive strategy (§12/§38.8).

Moved from ``zugzwang_chess/strategies`` (ZGW-0101): the strategy drives the
runtime ``CognitiveLoop`` over ``context.decision_session`` +
``context.backend``, so a chess package can never import runtime internals
(TEST-062) while the decision mechanics stay in the runtime where the
journal, the broker and the budget authority live.

Descriptor: the conservative default R7/H4/K0 mandated while the human gate
G-CB-01 is pending (§48.3) — no regime bump is self-granted by code. Every
``CallRecord`` in the trace comes from an effective ``infer`` call: usage,
cost, latency and fingerprints are the execution's own; an unavailable datum
stays unknown instead of an invented zero.
"""

from __future__ import annotations

from typing import Any

from zugzwang_core.ports.strategy import (
    CallRecord,
    Candidate,
    DecisionContext,
    DecisionTrace,
    StrategyDescriptor,
    Verdict,
)

from .loop import CognitiveLoop, LoopResult, ModelCallRecord

STRATEGY_ID = "chess.cognitive_navigation"
STRATEGY_VERSION = "0.2.0"


class CognitiveNavigationStrategy:
    """Adaptive L0 navigation driven by the typed ModelBackend (bounded)."""

    strategy_id = STRATEGY_ID
    strategy_version = STRATEGY_VERSION
    plugin_api = "zgw.plugin/v1alpha1"
    # The coordinator opens a §26.1 decision session for this strategy.
    requires_decision_session = True

    def __init__(self, *, max_rounds: int = 4) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        self._max_rounds = max_rounds

    @property
    def descriptor(self) -> StrategyDescriptor:
        # R7/H4 while G-CB-01 is pending (§48.3 default). declared K stays K0:
        # no knowledge exposure beyond the L0 packet until ratified otherwise.
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R7",
            declared_assistance_h="H4",
            declared_assistance_k="K0",
            consumes_legal_actions=True,
            produces_candidates=True,
            max_model_calls=self._max_rounds,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        """Run the productive loop and translate its result into a trace.

        ``context.decision_session`` is the authorized CognitiveBoard session
        (opened by the coordinator's factory); ``context.backend`` is the
        typed ModelBackend (RecordingBackend in production, the fake in
        offline tests). No proposal is invented here.
        """
        session = context.decision_session
        if session is None:
            raise ValueError("chess.cognitive_navigation requires DecisionContext.decision_session")
        if context.backend is None:
            raise ValueError("chess.cognitive_navigation requires DecisionContext.backend")
        journal = session.journal
        loop = CognitiveLoop(
            decision_id=session.decision_id,
            journal=journal,
            broker_factory=session.new_broker_for_round,
            backend=context.backend,
            context_artifact_id=session.round_context_artifact_id,
            model=context.model,
            max_rounds=self._max_rounds,
            interaction_mode=session.interaction_mode,
            shared_budget=session.budget,
            model_reservation_id=session.model_reservation_id,
        )
        result = await loop.run()
        return self._trace_from(result, context)

    def _trace_from(self, result: LoopResult, context: DecisionContext) -> DecisionTrace:
        verdicts = [
            Verdict(
                kind="tool_ok" if step.ok else "tool_failed",
                message=f"r{step.round_ordinal} {step.operation.get('tool')}"
                + (f" [{step.code}]" if step.code else ""),
            )
            for step in result.steps
        ]
        candidates: tuple[Candidate, ...] = ()
        if result.selected_action is not None:
            candidates = (Candidate(action=result.selected_action, origin="model"),)
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime=self.descriptor.declared_regime,
            calls=tuple(self._call_records(result.calls)),
            candidates=candidates,
            tool_invocations=tuple(
                f"{step.operation.get('tool')}@r{step.round_ordinal}" for step in result.steps
            ),
            verdicts=tuple(verdicts),
            selection_rationale={
                "status": result.status,
                "protocol_errors": result.protocol_errors,
                "rounds_executed": len(result.calls),
                "focus": result.decision_id,
            },
            final_action=result.selected_action,
            termination_reason="selected" if result.status == "COMMITTED" else "failed",
        )

    def _call_records(self, records: list[ModelCallRecord]) -> list[CallRecord]:
        out: list[CallRecord] = []
        for call in records:
            usage = call.usage
            out.append(
                CallRecord(
                    attempt_id=call.attempt_id,
                    request_fingerprint=call.request_fingerprint,
                    response_ok=call.response_ok,
                    usage=usage,
                    cost=call.cost,
                    latency_ms=call.latency_ms,
                    request_artifact_ref=call.request_artifact_id,
                    response_artifact_ref=call.response_artifact_id,
                    failure_code=call.failure_code,
                )
            )
        return out
