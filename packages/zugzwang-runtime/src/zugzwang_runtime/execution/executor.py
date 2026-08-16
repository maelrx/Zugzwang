"""Step executor: the state machine boundary of a single decision step.

Flow per design §7.2: observe → decide → verify → apply → commit.
The environment is the only authority that mutates canonical state.
Every stage emits scientific events before/after it runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zugzwang_core.domain.assistance import (
    AssistanceDeclared,
    AssistanceImpact,
    HClass,
    KClass,
    audit_assistance,
)
from zugzwang_core.domain.errors import IllegalActionError
from zugzwang_core.domain.events import EventAssistance, EventContext, EventEnvelope
from zugzwang_core.domain.state_machines import StepState, require_transition
from zugzwang_core.ports.environment import Environment, ObservationPolicy, Termination
from zugzwang_core.ports.strategy import DecisionContext, DecisionStrategy

from .artifacts import ArtifactStore
from .event_sink import EventSink

# The canonical environment executing state and transition is, by definition,
# H2 assistance (design §1.1 table). It is always included in the effective
# class computation.
_ENVIRONMENT_IMPACT = AssistanceImpact(h=HClass.H2, source="canonical_transition")


@dataclass(slots=True)
class StepExecutor:
    """Executes one step: strategy decision applied through the environment."""

    event_sink: EventSink
    artifact_store: ArtifactStore

    def _emit(
        self,
        *,
        step_id: str,
        event_type: str,
        payload: dict[str, Any],
        context: EventContext,
        assistance: EventAssistance | None = None,
        artifact_refs: tuple[str, ...] = (),
    ) -> EventEnvelope:
        sequence = self.event_sink.next_sequence("step", step_id)
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="step",
            stream_id=step_id,
            sequence=sequence,
            context=context,
            artifact_refs=artifact_refs,
            assistance=assistance,
        )

    async def execute(
        self,
        *,
        run_id: str,
        episode_id: str,
        step_id: str,
        strategy: DecisionStrategy,
        environment: Environment[Any, Any, Any],
        state: Any,
        observation_policy: ObservationPolicy,
        decision_context: DecisionContext,
        declared_h: str,
        declared_k: str,
    ) -> StepResult:
        """Run one step to COMMITTED (or a terminal failure)."""
        context = EventContext(run_id=run_id, episode_id=episode_id, step_id=step_id)
        current = StepState.PENDING

        def move(target: StepState) -> None:
            nonlocal current
            require_transition(current, target)
            current = target

        declared = AssistanceDeclared(h=HClass[declared_h], k=KClass[declared_k])

        move(StepState.OBSERVING)
        observation = environment.observe(state, observation_policy)
        self.event_sink.append(
            self._emit(step_id=step_id, event_type="step.observing", payload={}, context=context)
        )

        move(StepState.DECIDING)
        try:
            trace = await strategy.decide(observation, decision_context)
        except IllegalActionError:
            raise
        except Exception:
            await self._fail(
                step_id=step_id,
                context=context,
                current=current,
                event_type="step.provider_error",
                payload={"stable_code": "ZGZ-PROVIDER_TRANSPORT-000"},
            )
            return StepResult.failed(step_id, declared)

        impacts = (_ENVIRONMENT_IMPACT, *trace.assistance_impacts)
        audit = audit_assistance(declared, impacts)
        self.event_sink.append(
            self._emit(
                step_id=step_id,
                event_type="step.decided",
                payload={
                    "strategy_id": trace.strategy_id,
                    "strategy_version": trace.strategy_version,
                    "regime": trace.declared_regime,
                    "calls": len(trace.calls),
                    "termination_reason": trace.termination_reason,
                },
                context=context,
                assistance=EventAssistance(
                    h=audit.effective_h, k=audit.effective_k, source="decision"
                ),
            )
        )

        if trace.final_action is None:
            await self._fail(
                step_id=step_id,
                context=context,
                current=current,
                event_type="step.no_action",
                payload={"reason": trace.termination_reason},
            )
            return StepResult.failed(step_id, declared)

        move(StepState.VERIFYING)
        legal_actions = environment.legal_actions(state)
        action = trace.final_action
        if action not in legal_actions.actions:
            await self._fail(
                step_id=step_id,
                context=context,
                current=current,
                event_type="step.illegal_action",
                payload={"action": str(action), "legal": [str(a) for a in legal_actions.actions]},
            )
            return StepResult.failed(step_id, declared)

        move(StepState.APPLYING)
        transition = environment.transition(state, action)

        move(StepState.COMMITTED)
        snapshot_payload = environment.snapshot(transition.state)
        snapshot_ref = self.artifact_store.put(snapshot_payload)
        self.event_sink.append(
            self._emit(
                step_id=step_id,
                event_type="step.committed",
                payload={
                    "action": str(action),
                    "terminal": transition.terminal,
                    "assistance_violated": audit.violated,
                },
                context=context,
                artifact_refs=(snapshot_ref.as_id(),),
            )
        )
        return StepResult(
            step_id=step_id,
            state=StepState.COMMITTED,
            new_state=transition.state,
            action=action,
            terminal=transition.terminal,
            termination=transition.termination,
            violations=audit.violations,
            effective_h=audit.effective_h.name,
            effective_k=audit.effective_k.name,
        )

    async def _fail(
        self,
        *,
        step_id: str,
        context: EventContext,
        current: StepState,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if current is not StepState.TERMINAL_FAILURE:
            require_transition(current, StepState.TERMINAL_FAILURE)
        self.event_sink.append(
            self._emit(step_id=step_id, event_type=event_type, payload=payload, context=context)
        )


@dataclass(frozen=True, slots=True)
class StepResult:
    step_id: str
    state: StepState
    new_state: Any
    action: Any
    terminal: bool
    termination: Termination | None
    violations: tuple[str, ...]
    effective_h: str
    effective_k: str

    @classmethod
    def failed(cls, step_id: str, declared: AssistanceDeclared) -> StepResult:
        return cls(
            step_id=step_id,
            state=StepState.TERMINAL_FAILURE,
            new_state=None,
            action=None,
            terminal=False,
            termination=None,
            violations=(),
            effective_h=declared.h.name,
            effective_k=declared.k.name,
        )
