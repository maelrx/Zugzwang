"""Run coordinator: drives a resolved condition to completion (M0: sequential).

M1 adds concurrency limits, single-writer persistence and interrupt/resume.
The vertical slice here already exercises the full step state machine and
emits the scientific event stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zugzwang_core.domain.assistance import HClass, KClass
from zugzwang_core.domain.budgets import BudgetLedger, BudgetSpec
from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.events import EventContext, EventEnvelope
from zugzwang_core.domain.ids import new_id
from zugzwang_core.domain.manifests import ResolvedCondition, ResolvedManifest
from zugzwang_core.ports.environment import Environment, EpisodeSpec, ObservationPolicy
from zugzwang_core.ports.model import ModelBackend, ModelRef
from zugzwang_core.ports.strategy import DecisionContext, DecisionStrategy

from ..coercions import as_int
from .artifacts import ArtifactStore
from .event_sink import EventSink
from .executor import StepExecutor, StepResult
from .registry import PluginRegistry


@dataclass(slots=True)
class EpisodeRecord:
    episode_id: str
    condition_index: int
    episode_index: int
    seed: int
    outcome: str
    steps_committed: int = 0
    steps_failed: int = 0
    violations: tuple[str, ...] = ()
    effective_h: str = "H0"
    effective_k: str = "K0"
    final_state_snapshot_ref: str | None = None


@dataclass(slots=True)
class RunOutcome:
    run_id: str
    status: str
    episodes: list[EpisodeRecord]
    budget_used: dict[str, Any]
    started_at: str
    finished_at: str
    events: tuple[EventEnvelope, ...] = ()

    @classmethod
    def create(cls, run_id: str, started_at: str) -> RunOutcome:
        return cls(
            run_id=run_id,
            status="COMPLETED",
            episodes=[],
            budget_used={},
            started_at=started_at,
            finished_at="",
        )


class RunCoordinator:
    """Executes one condition's episodes with budgets and events."""

    def __init__(
        self,
        registry: PluginRegistry,
        event_sink: EventSink,
        artifact_store: ArtifactStore,
        backend: ModelBackend,
    ) -> None:
        self._registry = registry
        self._event_sink = event_sink
        self._artifact_store = artifact_store
        self._backend = backend
        self._step_executor = StepExecutor(event_sink=event_sink, artifact_store=artifact_store)

    def _emit_run_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        sequence: int,
    ) -> EventEnvelope:
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="run",
            stream_id=run_id,
            sequence=sequence,
            context=EventContext(run_id=run_id),
        )

    async def execute(self, resolved: ResolvedManifest, condition: ResolvedCondition) -> RunOutcome:
        run_id = str(new_id("run"))
        started_at = utc_now()
        self._event_sink.append(
            self._emit_run_event(
                run_id,
                "run.started",
                {"experiment": resolved.experiment_name, "condition_id": condition.condition_id},
                0,
            )
        )

        ledger = BudgetLedger(self._to_domain_budget(condition))
        task_config = condition.task.config
        episodes_count = as_int(task_config.get("episodes"), 1)
        max_steps = as_int(task_config.get("max_steps"), 10)

        outcome = RunOutcome.create(run_id=run_id, started_at=to_iso_z(started_at))

        for episode_index in range(episodes_count):
            episode = await self._run_episode(
                run_id=run_id,
                condition=condition,
                condition_index=condition.index,
                episode_index=episode_index,
                max_steps=max_steps,
                ledger=ledger,
                run_seed=resolved.source.spec.seed,
            )
            outcome.episodes.append(episode)

        if any(e.outcome == "failed" for e in outcome.episodes):
            outcome.status = "FAILED"

        effective_h = max((HClass[e.effective_h] for e in outcome.episodes), default=HClass.H0)
        effective_k = max((KClass[e.effective_k] for e in outcome.episodes), default=KClass.K0)
        outcome.finished_at = to_iso_z(utc_now())
        self._event_sink.append(
            self._emit_run_event(
                run_id,
                "run.finalized",
                {
                    "status": outcome.status,
                    "episodes": len(outcome.episodes),
                    "effective_assistance": {"h": effective_h.name, "k": effective_k.name},
                    "budget": {
                        "calls": str(ledger.used("calls")),
                        "failed_calls": str(ledger.used("failed_calls")),
                    },
                },
                1,
            )
        )
        outcome.events = self._event_sink.all_events()
        outcome.budget_used = {
            "calls": str(ledger.used("calls")),
            "input_tokens": str(ledger.used("input_tokens")),
            "output_tokens": str(ledger.used("output_tokens")),
            "failed_calls": str(ledger.used("failed_calls")),
        }
        return outcome

    async def _run_episode(
        self,
        *,
        run_id: str,
        condition: ResolvedCondition,
        condition_index: int,
        episode_index: int,
        max_steps: int,
        ledger: BudgetLedger,
        run_seed: int,
    ) -> EpisodeRecord:
        from zugzwang_core.domain.seeds import derive_seed

        episode_id = str(new_id("ep"))
        seed = derive_seed(run_seed, condition_index, episode_index)
        environment = self._environment_for(condition)
        strategy = self._strategy_for(condition)
        model = self._model_for(condition)

        episode_spec = EpisodeSpec(
            task_type=condition.task.plugin,
            seed=seed,
            config=dict(condition.task.config),
        )
        state = environment.initial_state(episode_spec)
        observation_policy = ObservationPolicy(settings=dict(condition.protocol.observation))

        self._emit_episode_event(episode_id, run_id, "episode.started", {"seed": seed})
        record = EpisodeRecord(
            episode_id=episode_id,
            condition_index=condition_index,
            episode_index=episode_index,
            seed=seed,
            outcome="completed",
        )

        step_ordinal = 0
        while True:
            step_id = str(new_id("stp"))
            decision_context = DecisionContext(
                run_id=run_id,
                episode_id=episode_id,
                step_id=step_id,
                model=model,
                backend=self._backend,
                tools={},
                seed=seed,
                config={},
                artifact_store=self._artifact_store,
            )
            result: StepResult = await self._step_executor.execute(
                run_id=run_id,
                episode_id=episode_id,
                step_id=step_id,
                strategy=strategy,
                environment=environment,
                state=state,
                observation_policy=observation_policy,
                decision_context=decision_context,
                declared_h=condition.protocol.declared_assistance,
                declared_k=condition.protocol.declared_knowledge,
            )
            if result.state.value == "COMMITTED":
                record.steps_committed += 1
                state = result.new_state
                record.violations = result.violations
                record.effective_h = result.effective_h
                record.effective_k = result.effective_k
                snapshot_payload = environment.snapshot(state)
                snapshot_ref = self._artifact_store.put(snapshot_payload)
                record.final_state_snapshot_ref = snapshot_ref.as_id()
                if result.terminal:
                    record.outcome = "completed"
                    break
                step_ordinal += 1
                if step_ordinal >= max_steps:
                    record.outcome = "max_steps"
                    break
                continue
            record.steps_failed += 1
            record.outcome = "failed"
            break

        self._emit_episode_event(
            episode_id,
            run_id,
            "episode.completed",
            {
                "outcome": record.outcome,
                "steps_committed": record.steps_committed,
                "steps_failed": record.steps_failed,
                "violations": list(record.violations),
            },
        )
        return record

    def _emit_episode_event(
        self,
        episode_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        sequence = self._event_sink.next_sequence("episode", episode_id)
        self._event_sink.append(
            EventEnvelope.create(
                event_type=event_type,
                payload=payload,
                stream_type="episode",
                stream_id=episode_id,
                sequence=sequence,
                context=EventContext(run_id=run_id, episode_id=episode_id),
            )
        )

    def _environment_for(self, condition: ResolvedCondition) -> Environment[Any, Any, Any]:
        task_plugin = condition.task.plugin
        if task_plugin == "fake.counter":
            from ..fakes import CounterEnvironment

            return CounterEnvironment()
        raise ValueError(f"no environment for task {task_plugin!r}")

    def _strategy_for(self, condition: ResolvedCondition) -> DecisionStrategy:
        for player in condition.players.values():
            if player.model is not None and player.model.strategy:
                strategy_id = player.model.strategy
                if strategy_id == "fake.direct":
                    from ..fakes import FakeDirectStrategy

                    return FakeDirectStrategy()
                raise ValueError(f"no strategy for {strategy_id!r}")
        raise ValueError("no model-driven player found")

    def _model_for(self, condition: ResolvedCondition) -> ModelRef:
        for player in condition.players.values():
            if player.model is not None:
                return ModelRef(
                    backend=player.model.backend or "fake.backend",
                    provider=player.model.provider or "fake",
                    model=player.model.model or "scripted",
                )
        raise ValueError("no model-driven player found")

    @staticmethod
    def _to_domain_budget(condition: ResolvedCondition) -> BudgetSpec:
        b = condition.budget
        return BudgetSpec(
            max_calls=b.max_calls,
            max_input_tokens=b.max_input_tokens,
            max_output_tokens=b.max_output_tokens,
            max_total_tokens=b.max_total_tokens,
            max_usd=None,
            max_wall_time_seconds=None,
            max_failed_calls=b.max_failed_calls,
            max_concurrent_episodes=b.max_concurrent_episodes,
            max_attempts_per_step=b.max_attempts,
            per_call_timeout_seconds=None,
        )
