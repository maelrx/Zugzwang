"""Durable run coordinator (M1, design §10).

Concurrent episodes over a bounded semaphore; every projection change and
scientific event flows through the single PersistenceWriter. The step commit
unit (projection + checkpoint + event) is atomic. Interrupt marks the run
INTERRUPTED with a safe checkpoint; resume continues from the first
non-COMMITTED step without repeating committed work.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from zugzwang_core.domain.budgets import BudgetLedger, BudgetSpec
from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.events import EventContext, EventEnvelope
from zugzwang_core.domain.ids import new_id
from zugzwang_core.domain.manifests import ResolvedCondition, ResolvedManifest
from zugzwang_core.domain.state_machines import EpisodeState, RunState
from zugzwang_core.ports.environment import Environment, EpisodeSpec, ObservationPolicy
from zugzwang_core.ports.model import ModelBackend, ModelRef
from zugzwang_core.ports.strategy import DecisionContext, DecisionStrategy

from ..artifacts.cas import ContentAddressedStore
from ..persistence.event_sink import PersistentEventSink
from ..persistence.repositories import (
    CheckpointRepository,
    EpisodeRepository,
    RunRepository,
    StepRepository,
)
from ..persistence.writer import (
    CommitStepCommand,
    FinalizeEpisodeCommand,
    FinalizeRunCommand,
    InsertEpisodeCommand,
    InsertStepCommand,
    PersistenceWriter,
    UpdateEpisodeCommand,
    UpsertRunCommand,
)
from .backend_caller import RecordingBackend
from .rate_limiting import RateLimiter
from .registry import PluginRegistry


class DurableRunCoordinator:
    """Executes conditions durably: concurrent, interruptible, resumable."""

    def __init__(
        self,
        *,
        registry: PluginRegistry,
        backend: ModelBackend,
        writer: PersistenceWriter,
        event_sink: PersistentEventSink,
        artifact_store: ContentAddressedStore,
        runs: RunRepository,
        episodes: EpisodeRepository,
        steps: StepRepository,
        checkpoints: CheckpointRepository,
        rate_limiter: RateLimiter,
    ) -> None:
        self._registry = registry
        self._backend = backend
        self._writer = writer
        self._event_sink = event_sink
        self._artifact_store = artifact_store
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._checkpoints = checkpoints
        self._rate_limiter = rate_limiter

    async def start_and_run(
        self,
        resolved: ResolvedManifest,
        condition: ResolvedCondition,
        stop_event: asyncio.Event,
    ) -> str:
        run_id = str(new_id("run"))
        protocol = condition.protocol
        now = to_iso_z(utc_now())
        self._writer.enqueue(
            UpsertRunCommand(
                row={
                    "run_id": run_id,
                    "condition_id": condition.condition_id,
                    "status": RunState.RUNNING.value,
                    "protocol_hash": resolved.protocol_hash,
                    "declared_assistance": protocol.declared_assistance,
                    "started_at": now,
                    "projection_version": 0,
                }
            )
        )
        self._emit_run_event(run_id, "run.started", {"experiment": resolved.experiment_name})
        try:
            await self._run_episodes(run_id, resolved, condition, stop_event)
        except asyncio.CancelledError:
            await self._writer.flush()
            self._writer.enqueue(
                FinalizeRunCommand(
                    run_id=run_id,
                    run_values={"status": RunState.INTERRUPTED.value},
                    envelope=self._run_envelope(run_id, "run.interrupted", {"reason": "cancelled"}),
                )
            )
            raise
        return run_id

    async def resume(
        self,
        run_id: str,
        resolved: ResolvedManifest,
        stop_event: asyncio.Event,
        condition: ResolvedCondition | None = None,
    ) -> None:
        """Continue an interrupted run from its first non-COMMITTED step."""
        row = self._runs.get_run(run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found in this workspace")
        if condition is None:
            condition = next(
                (c for c in resolved.conditions if c.condition_id == row["condition_id"]),
                resolved.conditions[0],
            )
        self._writer.enqueue(
            UpsertRunCommand(
                row={
                    "run_id": run_id,
                    "status": RunState.RUNNING.value,
                },
                update=True,
            )
        )
        self._emit_run_event(run_id, "run.resumed", {})
        await self._run_episodes(run_id, resolved, condition, stop_event, resume=True)

    async def _run_episodes(
        self,
        run_id: str,
        resolved: ResolvedManifest,
        condition: ResolvedCondition,
        stop_event: asyncio.Event,
        resume: bool = False,
    ) -> None:
        task_config = condition.task.config
        from ..coercions import as_int

        episodes_count = as_int(task_config.get("episodes"), 1)
        max_concurrency = condition.budget.max_concurrent_episodes
        ledger = BudgetLedger(self._to_domain_budget(condition))
        ledger_lock = asyncio.Lock()

        if resume:
            pending_episodes = await self._resume_work_items(run_id, condition)
        else:
            pending_episodes = self._episode_work_items(run_id, resolved, condition, episodes_count)
        semaphore = asyncio.Semaphore(max_concurrency)
        episodes_failed = 0
        episodes_completed = 0

        async def run_one(work: dict[str, Any]) -> None:
            nonlocal episodes_failed, episodes_completed
            async with semaphore:
                try:
                    outcome = await self._run_episode(
                        run_id=run_id,
                        condition=condition,
                        work=work,
                        ledger=ledger,
                        ledger_lock=ledger_lock,
                        stop_event=stop_event,
                    )
                except Exception as exc:
                    outcome = "failed"
                    self._writer.enqueue(
                        FinalizeEpisodeCommand(
                            episode_id=work["episode_id"],
                            episode_values={
                                "status": EpisodeState.FAILED.value,
                                "outcome": "error",
                            },
                            envelope=self._episode_envelope(
                                run_id,
                                work["episode_id"],
                                "episode.failed",
                                {
                                    "reason": getattr(exc, "stable_code", "internal"),
                                    "detail": str(exc),
                                },
                            ),
                        )
                    )
            if outcome == "failed":
                episodes_failed += 1
            elif outcome == "completed":
                episodes_completed += 1

        async with asyncio.TaskGroup() as group:
            for work in pending_episodes:
                group.create_task(run_one(work))

        status = RunState.COMPLETED.value if episodes_failed == 0 else RunState.FAILED.value
        if stop_event.is_set():
            status = RunState.INTERRUPTED.value
        self._writer.enqueue(
            FinalizeRunCommand(
                run_id=run_id,
                run_values={
                    "status": status,
                    "finished_at": to_iso_z(utc_now()),
                    "effective_assistance": "H2",
                },
                envelope=self._run_envelope(
                    run_id,
                    "run.finalized",
                    {
                        "status": status,
                        "episodes_completed": episodes_completed,
                        "episodes_failed": episodes_failed,
                    },
                ),
            )
        )

    def _episode_work_items(
        self,
        run_id: str,
        resolved: ResolvedManifest,
        condition: ResolvedCondition,
        count: int,
    ) -> list[dict[str, Any]]:
        from zugzwang_core.domain.seeds import derive_seed

        slots = self._task_slots(condition)
        items: list[dict[str, Any]] = []
        for index, slot in enumerate(slots):
            episode_id = str(new_id("ep"))
            seed = derive_seed(resolved.source.spec.seed, condition.index, index)
            self._writer.enqueue(
                InsertEpisodeCommand(
                    row={
                        "episode_id": episode_id,
                        "run_id": run_id,
                        "ordinal": index,
                        "task_type": condition.task.plugin,
                        "seed": seed,
                        "status": EpisodeState.PENDING.value,
                        "config_json": slot,
                    }
                )
            )
            items.append({"episode_id": episode_id, "ordinal": index, "seed": seed, **slot})
        return items

    def _task_slots(self, condition: ResolvedCondition) -> list[dict[str, Any]]:
        """Deterministic episode slots per task kind.

        Full games with paired openings expand openings x colors (FR-030);
        reconstruction expands move sequences; move-selection is a single slot.
        """
        config = condition.task.config
        kind = self._task_kind(condition)
        if kind == "full-game" and config.get("paired_colors"):
            openings = config.get("openings")
            opening_list = (
                [str(o) for o in openings]
                if isinstance(openings, list)
                else [str(config.get("start_fen", START_FEN_DEFAULT))]
            )
            return [
                {"start_fen": opening, "model_color": color}
                for opening in opening_list
                for color in ("white", "black")
            ]
        if kind == "state-reconstruction":
            sequences = config.get("move_sequences")
            if isinstance(sequences, list):
                slots: list[dict[str, Any]] = []
                for sequence in sequences:
                    raw_sequence: list[Any] = list(cast(list[Any], sequence))
                    slots.append({"move_prefix": [str(m) for m in raw_sequence]})
                return slots
        if kind == "move-selection":
            prefix = config.get("move_prefix")
            return [{"move_prefix": ([str(m) for m in prefix] if isinstance(prefix, list) else [])}]
        if kind == "counter":
            from ..coercions import as_int

            return [{} for _ in range(as_int(config.get("episodes"), 1))]
        return [{}]

    async def _resume_work_items(
        self, run_id: str, condition: ResolvedCondition
    ) -> list[dict[str, Any]]:
        rows = self._episodes.for_run(run_id)
        items: list[dict[str, Any]] = []
        for row in rows:
            if row["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
                continue
            slot = dict(row.get("config_json") or {})
            items.append(
                {
                    "episode_id": row["episode_id"],
                    "ordinal": row["ordinal"],
                    "seed": row["seed"],
                    "resume": True,
                    **slot,
                }
            )
        return items

    async def _rebuild_state(
        self,
        run_id: str,
        episode_id: str,
        environment: Environment[Any, Any, Any],
        initial_state: Any,
    ) -> tuple[Any, int]:
        """Rebuild episode state from committed steps (design §10.6).

        Order: restore from the last committed snapshot if present; otherwise
        replay committed actions from the initial state. The first
        non-COMMITTED step becomes the continuation point. A completed
        provider call that was committed is never repeated.
        """
        rows = self._steps.for_episode(episode_id)
        committed = [r for r in rows if r["status"] == "COMMITTED"]
        if not committed:
            return initial_state, 0
        last = committed[-1]
        state = initial_state
        if last.get("transition_artifact_id"):
            from zugzwang_core.domain.artifacts import ArtifactRef

            ref = ArtifactRef.parse(last["transition_artifact_id"])
            payload = self._artifact_store.get(ref)
            state = environment.restore(payload)
        else:
            for row in committed:
                action_json: dict[str, Any] = dict(row.get("action_json") or {})
                action = action_json.get("action")
                if action is not None:
                    state = environment.transition(state, action).state
        return state, len(committed)

    async def _run_episode(
        self,
        *,
        run_id: str,
        condition: ResolvedCondition,
        work: dict[str, Any],
        ledger: BudgetLedger,
        ledger_lock: asyncio.Lock,
        stop_event: asyncio.Event,
    ) -> str:
        episode_id = work["episode_id"]
        seed = work["seed"]
        environment = self._environment_for(condition)
        strategy = self._strategy_for(condition)
        model = self._model_for(condition)
        recording_backend = RecordingBackend(
            self._backend,
            writer=self._writer,
            event_sink=self._event_sink,
            max_transport_retries=condition.protocol.retries.transport,
            artifact_store=self._artifact_store,
            capture_raw_requests=condition.artifacts.raw_requests,
            capture_raw_responses=condition.artifacts.raw_responses,
        )

        task_kind = self._task_kind(condition)
        max_steps = self._max_steps_for(condition, task_kind)
        episode_config = dict(condition.task.config)
        if work.get("start_fen"):
            episode_config["start_fen"] = work["start_fen"]
        if work.get("model_color"):
            episode_config["model_color"] = work["model_color"]
        if work.get("move_prefix"):
            episode_config["move_prefix"] = work["move_prefix"]
        spec = EpisodeSpec(task_type=condition.task.plugin, seed=seed, config=episode_config)
        state = environment.initial_state(spec)
        if task_kind == "state-reconstruction" and work.get("move_prefix"):
            apply_moves = getattr(environment, "state_from_moves", None)
            if callable(apply_moves):
                state = apply_moves(list(work["move_prefix"]))
        observation_policy = ObservationPolicy(settings=dict(condition.protocol.observation))
        start_ordinal = 0

        if work.get("resume"):
            state, start_ordinal = await self._rebuild_state(run_id, episode_id, environment, state)

        initial_snapshot = self._artifact_store.put(environment.snapshot(state))
        if not work.get("resume"):
            self._writer.enqueue(
                UpdateEpisodeCommand(
                    episode_id=episode_id,
                    values={"initial_state_artifact_id": initial_snapshot.as_id()},
                )
            )
        self._emit_episode_event(run_id, episode_id, "episode.started", {"seed": seed})

        if _state_is_terminal(state):
            self._writer.enqueue(
                FinalizeEpisodeCommand(
                    episode_id=episode_id,
                    episode_values={
                        "status": EpisodeState.COMPLETED.value,
                        "outcome": "completed",
                        "final_state_artifact_id": initial_snapshot.as_id(),
                        "effective_assistance": "H2",
                    },
                    envelope=self._episode_envelope(
                        run_id,
                        episode_id,
                        "episode.completed",
                        {"steps": start_ordinal, "reason": "already_terminal"},
                    ),
                )
            )
            return "completed"

        opponent = self._opponent_for(condition)
        single_player = self._single_player(condition)
        model_color = self._model_color(condition)
        max_steps = self._max_steps_for(condition, task_kind)
        ordinal = start_ordinal
        while True:
            if stop_event.is_set():
                self._writer.enqueue(
                    FinalizeEpisodeCommand(
                        episode_id=episode_id,
                        episode_values={"status": EpisodeState.INTERRUPTED.value},
                        envelope=self._episode_envelope(
                            run_id, episode_id, "episode.interrupted", {}
                        ),
                    )
                )
                return "interrupted"

            if not single_player and getattr(state, "side_to_move", model_color) != model_color:
                if opponent is None:
                    await self._fail_step(run_id, episode_id, str(new_id("stp")), "no_opponent")
                    self._writer.enqueue(
                        FinalizeEpisodeCommand(
                            episode_id=episode_id,
                            episode_values={
                                "status": EpisodeState.FAILED.value,
                                "outcome": "failed",
                            },
                            envelope=self._episode_envelope(
                                run_id, episode_id, "episode.failed", {"reason": "no_opponent"}
                            ),
                        )
                    )
                    return "failed"
                outcome = await self._opponent_step(
                    run_id=run_id,
                    episode_id=episode_id,
                    ordinal=ordinal,
                    seed=seed,
                    condition=condition,
                    environment=environment,
                    state=state,
                    opponent=opponent,
                )
                if outcome is None:
                    await self._fail_step(run_id, episode_id, str(new_id("stp")), "opponent_error")
                    self._writer.enqueue(
                        FinalizeEpisodeCommand(
                            episode_id=episode_id,
                            episode_values={
                                "status": EpisodeState.FAILED.value,
                                "outcome": "failed",
                            },
                            envelope=self._episode_envelope(
                                run_id, episode_id, "episode.failed", {"reason": "opponent_error"}
                            ),
                        )
                    )
                    return "failed"
                state = outcome
                ordinal += 1
                if self._is_episode_complete(environment, state, ordinal, max_steps):
                    return await self._complete_episode(
                        run_id, episode_id, environment, state, ordinal, "completed"
                    )
                continue

            step_id = str(new_id("stp"))
            self._writer.enqueue(
                InsertStepCommand(
                    row={
                        "step_id": step_id,
                        "episode_id": episode_id,
                        "ordinal": ordinal,
                        "actor_id": str(model),
                        "status": "DECIDING",
                    }
                )
            )
            self._emit_step_event(run_id, episode_id, step_id, "step.started", {})

            if task_kind == "state-reconstruction":
                outcome = await self._reconstruction_step(
                    run_id=run_id,
                    episode_id=episode_id,
                    step_id=step_id,
                    ordinal=ordinal,
                    seed=seed,
                    condition=condition,
                    environment=environment,
                    state=state,
                    strategy=strategy,
                    model=model,
                    recording_backend=recording_backend,
                    observation_policy=observation_policy,
                    ledger=ledger,
                    ledger_lock=ledger_lock,
                )
                if not outcome:
                    return "failed"
                return await self._complete_episode(
                    run_id, episode_id, environment, state, ordinal + 1, "completed"
                )

            decision_context = DecisionContext(
                run_id=run_id,
                episode_id=episode_id,
                step_id=step_id,
                model=model,
                backend=recording_backend,
                tools={},
                seed=seed,
                config={},
                artifact_store=self._artifact_store,
            )
            observation = environment.observe(state, observation_policy)
            async with ledger_lock:
                try:
                    ledger.check_limits_or_raise()
                    ledger.reserve("calls", 1)
                except Exception as exc:
                    self._writer.enqueue(
                        FinalizeEpisodeCommand(
                            episode_id=episode_id,
                            episode_values={
                                "status": EpisodeState.FAILED.value,
                                "outcome": "budget",
                            },
                            envelope=self._episode_envelope(
                                run_id,
                                episode_id,
                                "episode.failed",
                                {"reason": getattr(exc, "stable_code", "budget")},
                            ),
                        )
                    )
                    return "failed"

            try:
                trace = await strategy.decide(observation, decision_context)
            except Exception:
                trace = None
            async with ledger_lock:
                ledger.reconcile("calls", 1, 1)

            if trace is None or trace.final_action is None:
                await self._fail_step(run_id, episode_id, step_id, "no_action")
                self._writer.enqueue(
                    FinalizeEpisodeCommand(
                        episode_id=episode_id,
                        episode_values={"status": EpisodeState.FAILED.value, "outcome": "failed"},
                        envelope=self._episode_envelope(
                            run_id, episode_id, "episode.failed", {"step": ordinal}
                        ),
                    )
                )
                return "failed"

            legal_actions = environment.legal_actions(state)
            final_action = trace.final_action
            if isinstance(final_action, int):
                final_action = _resolve_index(final_action, legal_actions)
            action = _coerce_action(final_action, legal_actions)
            if action not in legal_actions.actions:
                await self._fail_step(run_id, episode_id, step_id, "illegal_action")
                self._writer.enqueue(
                    FinalizeEpisodeCommand(
                        episode_id=episode_id,
                        episode_values={"status": EpisodeState.FAILED.value, "outcome": "failed"},
                        envelope=self._episode_envelope(
                            run_id, episode_id, "episode.failed", {"step": ordinal}
                        ),
                    )
                )
                return "failed"

            transition = environment.transition(state, action)
            snapshot_ref = self._artifact_store.put(environment.snapshot(transition.state))

            committed_event = self._step_envelope(
                run_id,
                episode_id,
                step_id,
                "step.committed",
                {"action": str(action), "terminal": transition.terminal},
                artifact_refs=(snapshot_ref.as_id(),),
            )
            checkpoint_row = {
                "run_id": run_id,
                "stream_type": "step",
                "stream_id": step_id,
                "sequence_committed": 1,
                "state_artifact_id": snapshot_ref.as_id(),
                "schema_version": "zgw.event/v1alpha1",
                "created_at": to_iso_z(utc_now()),
            }
            self._writer.enqueue(
                CommitStepCommand(
                    step_id=step_id,
                    step_values={
                        "status": "COMMITTED",
                        "action_json": {"action": str(action)},
                        "transition_artifact_id": snapshot_ref.as_id(),
                        "committed_at": to_iso_z(utc_now()),
                    },
                    episode_id=episode_id,
                    episode_values={"status": EpisodeState.RUNNING.value},
                    envelope=committed_event,
                    checkpoint_row=checkpoint_row,
                )
            )
            state = transition.state
            ordinal += 1
            if transition.terminal:
                return await self._complete_episode(
                    run_id, episode_id, environment, state, ordinal, "completed"
                )
            if self._is_episode_complete(environment, state, ordinal, max_steps):
                return await self._complete_episode(
                    run_id, episode_id, environment, state, ordinal, "completed"
                )

    def _max_steps_for(self, condition: ResolvedCondition, task_kind: str) -> int:
        from ..coercions import as_int

        if task_kind == "full-game":
            return as_int(condition.task.config.get("max_plies"), 240)
        if task_kind in {"move-selection", "state-reconstruction"}:
            return 1
        return as_int(condition.task.config.get("max_steps"), 10)

    def _is_episode_complete(
        self, environment: Environment[Any, Any, Any], state: Any, ordinal: int, max_steps: int
    ) -> bool:
        if _state_is_terminal(state):
            return True
        return ordinal >= max_steps

    async def _complete_episode(
        self,
        run_id: str,
        episode_id: str,
        environment: Environment[Any, Any, Any],
        state: Any,
        ordinal: int,
        outcome: str,
    ) -> str:
        snapshot_ref = self._artifact_store.put(environment.snapshot(state))
        self._writer.enqueue(
            FinalizeEpisodeCommand(
                episode_id=episode_id,
                episode_values={
                    "status": EpisodeState.COMPLETED.value,
                    "outcome": outcome,
                    "final_state_artifact_id": snapshot_ref.as_id(),
                    "effective_assistance": "H2",
                },
                envelope=self._episode_envelope(
                    run_id, episode_id, "episode.completed", {"steps": ordinal}
                ),
            )
        )
        return "completed"

    async def _opponent_step(
        self,
        *,
        run_id: str,
        episode_id: str,
        ordinal: int,
        seed: int,
        condition: ResolvedCondition,
        environment: Environment[Any, Any, Any],
        state: Any,
        opponent: Any,
    ) -> Any | None:
        """One opponent ply: no provider calls, recorded as a committed step."""
        from zugzwang_core.domain.seeds import derive_step_seed

        step_id = str(new_id("stp"))
        self._writer.enqueue(
            InsertStepCommand(
                row={
                    "step_id": step_id,
                    "episode_id": episode_id,
                    "ordinal": ordinal,
                    "actor_id": getattr(opponent, "policy_id", "policy"),
                    "status": "DECIDING",
                }
            )
        )
        self._emit_step_event(run_id, episode_id, step_id, "step.started", {})
        legal_actions = environment.legal_actions(state)
        try:
            action = await opponent.choose(
                state, legal_actions.actions, derive_step_seed(seed, ordinal)
            )
        except Exception:
            return None
        if action not in legal_actions.actions:
            await self._fail_step(run_id, episode_id, step_id, "illegal_action")
            return None
        transition = environment.transition(state, action)
        snapshot_ref = self._artifact_store.put(environment.snapshot(transition.state))
        self._writer.enqueue(
            CommitStepCommand(
                step_id=step_id,
                step_values={
                    "status": "COMMITTED",
                    "action_json": {"action": str(action)},
                    "transition_artifact_id": snapshot_ref.as_id(),
                    "committed_at": to_iso_z(utc_now()),
                },
                episode_id=episode_id,
                episode_values={"status": EpisodeState.RUNNING.value},
                envelope=self._step_envelope(
                    run_id,
                    episode_id,
                    step_id,
                    "step.committed",
                    {"action": str(action), "terminal": transition.terminal},
                    artifact_refs=(snapshot_ref.as_id(),),
                ),
                checkpoint_row={
                    "run_id": run_id,
                    "stream_type": "step",
                    "stream_id": step_id,
                    "sequence_committed": 1,
                    "state_artifact_id": snapshot_ref.as_id(),
                    "schema_version": "zgw.event/v1alpha1",
                    "created_at": to_iso_z(utc_now()),
                },
            )
        )
        return transition.state

    async def _reconstruction_step(
        self,
        *,
        run_id: str,
        episode_id: str,
        step_id: str,
        ordinal: int,
        seed: int,
        condition: ResolvedCondition,
        environment: Environment[Any, Any, Any],
        state: Any,
        strategy: DecisionStrategy,
        model: ModelRef,
        recording_backend: Any,
        observation_policy: ObservationPolicy,
        ledger: BudgetLedger,
        ledger_lock: asyncio.Lock,
    ) -> bool:
        """A reconstruction step: the model predicts the FEN; no transition.

        Returns True when the episode should complete; None when failed.
        """
        decision_context = DecisionContext(
            run_id=run_id,
            episode_id=episode_id,
            step_id=step_id,
            model=model,
            backend=recording_backend,
            tools={},
            seed=seed,
            config={},
            artifact_store=self._artifact_store,
        )
        observation = environment.observe(state, observation_policy)
        async with ledger_lock:
            try:
                ledger.check_limits_or_raise()
                ledger.reserve("calls", 1)
            except Exception as exc:
                self._writer.enqueue(
                    FinalizeEpisodeCommand(
                        episode_id=episode_id,
                        episode_values={"status": EpisodeState.FAILED.value, "outcome": "budget"},
                        envelope=self._episode_envelope(
                            run_id,
                            episode_id,
                            "episode.failed",
                            {"reason": getattr(exc, "stable_code", "budget")},
                        ),
                    )
                )
                return False
        try:
            trace = await strategy.decide(observation, decision_context)
        except Exception:
            trace = None
        async with ledger_lock:
            ledger.reconcile("calls", 1, 1)

        if trace is None or trace.final_action is None:
            await self._fail_step(run_id, episode_id, step_id, "no_action")
            self._writer.enqueue(
                FinalizeEpisodeCommand(
                    episode_id=episode_id,
                    episode_values={"status": EpisodeState.FAILED.value, "outcome": "failed"},
                    envelope=self._episode_envelope(
                        run_id, episode_id, "episode.failed", {"reason": "no_action"}
                    ),
                )
            )
            return False

        predicted = str(trace.final_action).strip()
        from zugzwang_chess.codecs.fen import parse_fen

        try:
            predicted_state = parse_fen(predicted)
        except Exception as exc:
            await self._fail_step(run_id, episode_id, step_id, "parse_error")
            self._writer.enqueue(
                FinalizeEpisodeCommand(
                    episode_id=episode_id,
                    episode_values={"status": EpisodeState.FAILED.value, "outcome": "parse_error"},
                    envelope=self._episode_envelope(
                        run_id,
                        episode_id,
                        "episode.failed",
                        {"reason": getattr(exc, "stable_code", "parse_error")},
                    ),
                )
            )
            return False

        canonical = environment.snapshot(state)
        from zugzwang_chess.metrics.reconstruction import score_reconstruction

        assert predicted_state is not None
        scores = score_reconstruction(state.fen, predicted_state.fen)
        snapshot_ref = self._artifact_store.put(canonical)
        self._writer.enqueue(
            CommitStepCommand(
                step_id=step_id,
                step_values={
                    "status": "COMMITTED",
                    "action_json": {"action": predicted, "kind": "fen_prediction"},
                    "transition_artifact_id": snapshot_ref.as_id(),
                    "committed_at": to_iso_z(utc_now()),
                },
                episode_id=episode_id,
                episode_values={"status": EpisodeState.RUNNING.value},
                envelope=self._step_envelope(
                    run_id,
                    episode_id,
                    step_id,
                    "step.committed",
                    {
                        "action": predicted,
                        "terminal": False,
                        "reconstruction_scores": scores,
                    },
                    artifact_refs=(snapshot_ref.as_id(),),
                ),
                checkpoint_row={
                    "run_id": run_id,
                    "stream_type": "step",
                    "stream_id": step_id,
                    "sequence_committed": 1,
                    "state_artifact_id": snapshot_ref.as_id(),
                    "schema_version": "zgw.event/v1alpha1",
                    "created_at": to_iso_z(utc_now()),
                },
            )
        )
        return True

    async def _fail_step(self, run_id: str, episode_id: str, step_id: str, reason: str) -> None:
        self._emit_step_event(run_id, episode_id, step_id, f"step.{reason}", {})
        self._writer.enqueue(
            CommitStepCommand(
                step_id=step_id,
                step_values={"status": "TERMINAL_FAILURE"},
                episode_id=episode_id,
                episode_values={"status": EpisodeState.RUNNING.value},
                envelope=self._step_envelope(
                    run_id, episode_id, step_id, "step.terminal_failure", {"reason": reason}
                ),
                checkpoint_row={
                    "run_id": run_id,
                    "stream_type": "step",
                    "stream_id": step_id,
                    "sequence_committed": 1,
                    "state_artifact_id": None,
                    "schema_version": "zgw.event/v1alpha1",
                    "created_at": to_iso_z(utc_now()),
                },
            )
        )

    def _emit_run_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._event_sink.append(self._run_envelope(run_id, event_type, payload))

    def _run_envelope(self, run_id: str, event_type: str, payload: dict[str, Any]) -> EventEnvelope:
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="run",
            stream_id=run_id,
            sequence=0,
            context=EventContext(run_id=run_id),
        )

    def _emit_episode_event(
        self, run_id: str, episode_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        self._event_sink.append(self._episode_envelope(run_id, episode_id, event_type, payload))

    def _episode_envelope(
        self, run_id: str, episode_id: str, event_type: str, payload: dict[str, Any]
    ) -> EventEnvelope:
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="episode",
            stream_id=episode_id,
            sequence=0,
            context=EventContext(run_id=run_id, episode_id=episode_id),
        )

    def _emit_step_event(
        self, run_id: str, episode_id: str, step_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        self._event_sink.append(
            self._step_envelope(run_id, episode_id, step_id, event_type, payload)
        )

    def _step_envelope(
        self,
        run_id: str,
        episode_id: str,
        step_id: str,
        event_type: str,
        payload: dict[str, Any],
        artifact_refs: tuple[str, ...] = (),
    ) -> EventEnvelope:
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="step",
            stream_id=step_id,
            sequence=0,
            context=EventContext(run_id=run_id, episode_id=episode_id, step_id=step_id),
            artifact_refs=artifact_refs,
        )

    def _environment_for(self, condition: ResolvedCondition) -> Environment[Any, Any, Any]:
        if condition.task.plugin in {"fake.counter", "chess.tasks"}:
            if condition.task.plugin == "fake.counter":
                from ..fakes import CounterEnvironment

                return CounterEnvironment()
            from zugzwang_chess import StandardChessEnvironment

            return StandardChessEnvironment()
        raise ValueError(f"no environment for task {condition.task.plugin!r}")

    def _strategy_for(self, condition: ResolvedCondition) -> DecisionStrategy:
        for player in condition.players.values():
            if player.model is not None:
                if player.model.strategy == "fake.direct":
                    from ..fakes import FakeDirectStrategy

                    return FakeDirectStrategy()
                if player.model.strategy == "chess.direct":
                    from zugzwang_chess.strategies.direct import ChessDirectStrategy

                    return ChessDirectStrategy()
                if player.model.strategy == "chess.grounded":
                    from zugzwang_chess.strategies.grounded import GroundedStrategy

                    return GroundedStrategy()
                if player.model.strategy == "chess.reconstruct":
                    from zugzwang_chess.strategies.reconstruct import ReconstructStrategy

                    return ReconstructStrategy()
                if player.model.strategy == "chess.structured":
                    from zugzwang_chess.strategies.structured import StructuredStrategy

                    return StructuredStrategy()
                if player.model.strategy == "chess.repair":
                    from zugzwang_chess.strategies.repair import RepairStrategy

                    return RepairStrategy(
                        max_retries=condition.protocol.retries.parse
                        + condition.protocol.retries.illegal,
                        feedback=condition.protocol.retries.feedback,
                    )
        raise ValueError("no supported model-driven strategy found")

    def _model_for(self, condition: ResolvedCondition) -> ModelRef:
        for player in condition.players.values():
            if player.model is not None:
                return ModelRef(
                    backend=player.model.backend or "fake.backend",
                    provider=player.model.provider or "fake",
                    model=player.model.model or "scripted",
                )
        raise ValueError("no model-driven player found")

    def _task_kind(self, condition: ResolvedCondition) -> str:
        plugin = condition.task.plugin
        if plugin == "fake.counter":
            return "counter"
        return str(condition.task.config.get("kind", "full-game"))

    def _model_color(self, condition: ResolvedCondition) -> str:
        return str(condition.task.config.get("model_color", "white"))

    def _single_player(self, condition: ResolvedCondition) -> bool:
        return self._task_kind(condition) in {
            "counter",
            "move-selection",
            "state-reconstruction",
        }

    def _opponent_for(self, condition: ResolvedCondition):
        for player in condition.players.values():
            if player.policy is not None:
                plugin = player.policy.plugin
                if plugin == "chess.random-legal":
                    from zugzwang_chess import RandomLegalOpponent

                    return RandomLegalOpponent()
                if plugin == "chess.scripted":
                    from zugzwang_chess import ScriptedOpponent

                    script_raw = player.policy.config.get("script", ())
                    script = (
                        tuple(str(m) for m in script_raw)
                        if isinstance(script_raw, (list, tuple))
                        else ()
                    )
                    return ScriptedOpponent(script)
                if plugin == "fake.stay":
                    return None
        return None

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


START_FEN_DEFAULT = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _state_is_terminal(state: Any) -> bool:
    """Duck-typed terminality probe for v0.1 environment states."""
    terminal = getattr(state, "terminal", False)
    if callable(terminal):
        return bool(terminal())
    return bool(terminal)


def _resolve_index(index: int, legal_actions: Any) -> Any:
    """Map an opaque index into the frozen legal ordering (R1)."""
    if not 0 <= index < len(legal_actions.actions):
        raise IndexError(f"legal action index {index} out of range")
    return legal_actions.actions[index]


def _coerce_action(action: Any, legal_actions: Any) -> Any:
    """Wrap a string action into the environment's action type when needed."""
    if not legal_actions.actions:
        return action
    try:
        if action in legal_actions.actions:
            return action
    except TypeError:
        pass
    first = legal_actions.actions[0]
    if isinstance(action, str):
        from collections.abc import Callable

        constructor = cast(Callable[[str], Any], type(first))
        try:
            return constructor(action)
        except Exception:
            return action
    return action
