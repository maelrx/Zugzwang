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

from typing import Any, cast

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
        raw_config: Any = context.config.get("cognitive") or {}
        config = cast("dict[str, Any]", raw_config) if isinstance(raw_config, dict) else {}
        section_builder = self._section_builder(session, config)
        feedback = self._round_feedback(session, config)
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
            context_sections=section_builder,
            round_feedback=feedback,
        )
        result = await loop.run()
        return self._trace_from(result, context)

    # -- context wiring (§16/§18/§10: what the model actually receives) ---------

    def _decision_bindings(self, session: Any) -> dict[str, Any]:
        from sqlalchemy import text as _sql_text

        with session.journal.connect() as conn:
            row = conn.execute(
                _sql_text(
                    "SELECT memory_snapshot_id, skill_set_id FROM cb_decisions "
                    "WHERE decision_id = :id"
                ),
                {"id": session.decision_id},
            ).fetchone()
        return {
            "memory_snapshot_id": row[0] if row else None,
            "skill_set_id": row[1] if row else None,
        }

    def _section_builder(self, session: Any, config: dict[str, Any]):
        """Build the memory/skills context section from the REAL stores.

        Returns None when neither store is bound — memory OFF is observably
        absent from the request, never an empty placeholder (§16; HY-04).
        """
        memory_store = getattr(session, "memory_store", None)
        skill_registry = getattr(session, "skill_registry", None)
        bindings = self._decision_bindings(session)
        snapshot_id = bindings.get("memory_snapshot_id")
        skill_set_id = bindings.get("skill_set_id")
        skill_id = config.get("skill_id")

        def build(ordinal: int) -> str:
            sections: list[str] = []
            if memory_store is not None and snapshot_id:
                recalled = memory_store.recall(
                    snapshot_id=str(snapshot_id),
                    scope_kind="episode",
                    scope_owner_id="",
                    perspective="neutral",
                )
                lines = [
                    f"- {item.kind}/{item.epistemic_status}: {item.logical_memory_id} "
                    f"r{item.revision} [{item.eligibility_reason}]"
                    for item in recalled.items
                ]
                if lines:
                    sections.append(
                        "ELIGIBLE MEMORY (snapshot "
                        f"{snapshot_id}, frozen for this decision):\n" + "\n".join(lines)
                    )
            if skill_registry is not None and skill_set_id and skill_id:
                activation = skill_registry.activate(
                    skill_set_id=str(skill_set_id),
                    skill_id=str(skill_id),
                    requested=tuple(config.get("skill_capabilities", ())),
                )
                sections.append(
                    f"ACTIVE SKILL {activation.skill_id} v{activation.version} "
                    f"(set {skill_set_id}, frozen): "
                    f"capabilities={list(activation.capabilities)}"
                )
            return "\n\n".join(sections)

        if (memory_store is None or not snapshot_id) and not (
            skill_registry is not None and skill_set_id and skill_id
        ):
            return None
        return build

    def _round_feedback(self, session: Any, config: dict[str, Any]):
        """Revise the episode's plan from the REAL tool results of a round.

        The watched premise is the CB default: when a committed expansion
        reaches a terminal child, the premise ``position_terminal`` flips to
        true. A changed premise escalates the plan to needs_review via the
        plan store's own delta logic — never a silent continuation (§10.3).
        """
        plan_store = getattr(session, "plan_store", None)
        plan_id = config.get("plan_id")
        if plan_store is None or not plan_id:
            return None

        def feedback(ordinal: int, executed: list[dict[str, Any]]) -> None:
            view = plan_store.view_plan(str(plan_id))
            premises = dict(view.premises)
            changed = False
            for entry in executed:
                result: Any = entry.get("result")
                if not isinstance(result, dict):
                    continue
                raw_rows: Any = cast("dict[str, Any]", result).get("results") or []
                items: list[Any] = cast("list[Any]", raw_rows) if isinstance(raw_rows, list) else []
                for item in list(items):
                    row_data: Any = dict(cast(Any, item)) if isinstance(item, dict) else {}
                    terminal: Any = row_data.get("terminal")
                    if terminal is True and premises.get("position_terminal") != "true":
                        premises["position_terminal"] = "true"
                        changed = True
            if changed:
                plan_store.revise_plan(
                    plan_id=str(plan_id), status="needs_review", premises=premises
                )

        return feedback

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
        from zugzwang_core.domain.money import TokenUsage

        out: list[CallRecord] = []
        for call in records:
            # Unavailable usage stays UNKNOWN, never zero-invented (§22.2).
            usage = call.usage if call.usage is not None else TokenUsage()
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


class CognitiveNavigationStrategyDefinition:
    """Plugin entry exposing chess.cognitive_navigation (installed by runtime)."""

    @property
    def descriptor(self):  # type: ignore[no-untyped-def]
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        return PluginDescriptor(
            plugin_id="chess.cognitive_navigation",
            plugin_version="0.2.0",
            kind=PluginKind.STRATEGY,
            capabilities=("R7", "cognitive"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )

    def create(self, **kwargs: Any) -> CognitiveNavigationStrategy:
        rounds: Any = kwargs.get("max_rounds", 4)
        return CognitiveNavigationStrategy(max_rounds=int(rounds) if isinstance(rounds, int) else 4)


COGNITIVE_NAVIGATION_STRATEGY_ENTRY = CognitiveNavigationStrategyDefinition()
