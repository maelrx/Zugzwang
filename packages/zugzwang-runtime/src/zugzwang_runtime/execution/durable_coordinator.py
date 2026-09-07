"""Durable run coordinator (M1, design §10).

Concurrent episodes over a bounded semaphore; every projection change and
scientific event flows through the single PersistenceWriter. The step commit
unit (projection + checkpoint + event) is atomic. Interrupt marks the run
INTERRUPTED with a safe checkpoint; resume continues from the first
non-COMMITTED step without repeating committed work.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from zugzwang_core.domain.assistance import HClass, KClass
from zugzwang_core.domain.budgets import BudgetLedger, BudgetSpec
from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.events import EventAssistance, EventContext, EventEnvelope
from zugzwang_core.domain.ids import new_id
from zugzwang_core.domain.manifests import ResolvedCondition, ResolvedManifest
from zugzwang_core.domain.state_machines import EpisodeState, RunState
from zugzwang_core.ports.environment import Environment, EpisodeSpec, ObservationPolicy
from zugzwang_core.ports.model import ModelBackend, ModelRef
from zugzwang_core.ports.rules import ActionHandle, DecisionCapabilities
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
    UpdateStepCommand,
    UpsertRunCommand,
)
from .backend_caller import RecordingBackend
from .evidence import (
    decision_trace_payload,
    observation_artifact_payload,
    store_artifact,
    store_json_artifact,
)
from .legality import LegalityGateway
from .rate_limiting import RateLimiter
from .registry import PluginRegistry


class _ModelOpponent:
    """Use the same model strategy for the second side in explicit self-play."""

    version = "0.1.0"

    def __init__(
        self,
        *,
        run_id: str,
        episode_id: str,
        model: ModelRef,
        strategy: DecisionStrategy,
        backend: Any,
        environment: Environment[Any, Any, Any],
        observation_policy: ObservationPolicy,
        artifact_store: ContentAddressedStore,
        writer: PersistenceWriter,
        event_sink: PersistentEventSink,
        declared_h: str,
        declared_k: str,
        knowledge: tuple[Any, ...],
        config: dict[str, Any],
    ) -> None:
        self._run_id = run_id
        self._episode_id = episode_id
        self.policy_id = f"model-opponent/{model}"
        self._model = model
        self._strategy = strategy
        self._backend = backend
        self._environment = environment
        self._observation_policy = observation_policy
        self._artifact_store = artifact_store
        self._writer = writer
        self._event_sink = event_sink
        self._declared_h = declared_h
        self._declared_k = declared_k
        self._knowledge = knowledge
        self._config = config
        self._step_id: str | None = None
        self._last_effective_h = HClass.H2
        self._last_effective_k = KClass.K0

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "model": str(self._model),
            "effective_assistance": _assistance_string(
                self._last_effective_h, self._last_effective_k
            ),
        }

    def prepare_step(self, step_id: str) -> None:
        self._step_id = step_id

    async def choose(self, state: Any, legal_actions: tuple[Any, ...], seed: int) -> Any:
        if self._step_id is None:
            raise ValueError("model opponent step was not prepared")
        observation = self._environment.observe(state, self._observation_policy)
        state_ref = store_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=self._environment.snapshot(state),
        ).as_id()
        observation_ref = store_json_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=observation_artifact_payload(
                run_id=self._run_id,
                episode_id=self._episode_id,
                step_id=self._step_id,
                state=state,
                observation=cast(dict[str, Any], observation),
                policy_settings=cast(dict[str, Any], dict(self._observation_policy.settings)),
                declared_h=self._declared_h,
                declared_k=self._declared_k,
                state_ref=state_ref,
            ),
            media_type="application/vnd.zugzwang.observation+json",
            redaction_policy="standard",
        ).as_id()
        self._writer.enqueue(
            UpdateStepCommand(
                step_id=self._step_id,
                values={"observation_artifact_id": observation_ref},
            )
        )
        self._event_sink.append(
            self._step_envelope(
                "step.observation.created",
                {"state_fingerprint": _state_fingerprint(state)},
                artifact_refs=(observation_ref, state_ref),
            )
        )
        begin_decision = getattr(self._backend, "begin_decision", None)
        if callable(begin_decision):
            begin_decision()
        context = DecisionContext(
            run_id=self._run_id,
            episode_id=self._episode_id,
            step_id=self._step_id,
            model=self._model,
            backend=self._backend,
            tools={},
            seed=seed,
            config=self._config,
            artifact_store=self._artifact_store,
            knowledge=self._knowledge,
            state=state,
        )
        trace = await self._strategy.decide(observation, context)
        self._last_effective_h, self._last_effective_k = _merge_assistance(
            HClass.H2, KClass.K0, trace.assistance_impacts
        )
        trace_ref = store_json_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=decision_trace_payload(
                run_id=self._run_id,
                episode_id=self._episode_id,
                step_id=self._step_id,
                trace=trace,
                attempt_index=0,
                attempt_evidence=(
                    self._backend.evidence_for_current_decision()
                    if hasattr(self._backend, "evidence_for_current_decision")
                    else {}
                ),
            ),
            media_type="application/vnd.zugzwang.decision-trace+json",
            redaction_policy="standard",
        ).as_id()
        self._writer.enqueue(
            UpdateStepCommand(
                step_id=self._step_id,
                values={
                    "decision_trace_artifact_id": trace_ref,
                    "effective_assistance": _assistance_string(
                        self._last_effective_h, self._last_effective_k
                    ),
                },
            )
        )
        self._event_sink.append(
            self._step_envelope(
                "decision.trace.created",
                {"strategy_id": trace.strategy_id, "attempt_index": 0},
                artifact_refs=(trace_ref,),
            )
        )
        self._event_sink.append(
            self._step_envelope(
                "step.decided",
                {"strategy_id": trace.strategy_id, "calls": len(trace.calls)},
                artifact_refs=(trace_ref,),
            )
        )
        action_raw = trace.final_action
        if not isinstance(action_raw, str):
            raise ValueError("self-play model returned no action")
        from zugzwang_chess.environment.standard import ChessMove

        action = ChessMove(action_raw)
        if action not in legal_actions:
            raise ValueError(f"self-play model returned illegal move {action_raw!r}")
        return action

    def _step_envelope(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        artifact_refs: tuple[str, ...] = (),
    ) -> EventEnvelope:
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="step",
            stream_id=self._step_id or self._run_id,
            sequence=0,
            context=EventContext(
                run_id=self._run_id,
                episode_id=self._episode_id,
                step_id=self._step_id,
            ),
            artifact_refs=artifact_refs,
            assistance=EventAssistance(
                h=self._last_effective_h,
                k=self._last_effective_k,
                source="model_opponent",
            ),
        )


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
        cognitive_session_factory: Any | None = None,
        artifacts: Any | None = None,
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
        self._cognitive_session_factory = cognitive_session_factory
        self._artifacts = artifacts
        self._run_assistance: dict[str, tuple[HClass, KClass]] = {}
        self._run_assistance_violated: dict[str, bool] = {}

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
        knowledge = resolved.packets_for(condition)

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
                        knowledge=knowledge,
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
                    "effective_assistance": _assistance_string(
                        *self._run_assistance.get(run_id, (HClass.H2, KClass.K0))
                    ),
                    "assistance_violated": 1
                    if self._run_assistance_violated.get(run_id, False)
                    else 0,
                },
                envelope=self._run_envelope(
                    run_id,
                    "run.finalized",
                    {
                        "status": status,
                        "episodes_completed": episodes_completed,
                        "episodes_failed": episodes_failed,
                        "effective_assistance": _assistance_string(
                            *self._run_assistance.get(run_id, (HClass.H2, KClass.K0))
                        ),
                        "assistance_violated": self._run_assistance_violated.get(run_id, False),
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
            if payload.media_type == "application/octet-stream":
                # Bare-digest refs parse without a media type, but the
                # artifacts table records the true one (design §11.7:
                # metadata lives in the database). Resume is the only
                # reader of this path — fresh runs keep state in memory —
                # which is why the octet-stream default survived until the
                # real pilot (2026-09-06: "cannot restore chess state").
                payload = self._retype_payload(ref)
            state = environment.restore(payload)
        else:
            for row in committed:
                action_json: dict[str, Any] = dict(row.get("action_json") or {})
                action = action_json.get("action")
                if action is not None:
                    state = environment.transition(state, action).state
        return state, len(committed)

    def _retype_payload(self, ref: Any) -> Any:
        """Rehydrate a CAS payload with its database-recorded media type.

        Falls back to the octet-stream payload (and lets ``restore`` raise
        its honest error) when the artifacts row is absent — never invents
        a type.
        """
        from zugzwang_core.domain.artifacts import ArtifactPayload

        payload = self._artifact_store.get(ref)
        get_row = getattr(self._artifacts, "get", None)
        if get_row is None:
            return payload
        row: dict[str, Any] | None = cast("dict[str, Any] | None", get_row(ref.as_id()))
        if not row:
            return payload
        media_type = row.get("media_type")
        if not isinstance(media_type, str) or "/" not in media_type:
            return payload
        return ArtifactPayload(media_type=media_type, data=payload.data)

    async def _run_episode(
        self,
        *,
        run_id: str,
        knowledge: tuple[Any, ...],
        condition: ResolvedCondition,
        work: dict[str, Any],
        ledger: BudgetLedger,
        ledger_lock: asyncio.Lock,
        stop_event: asyncio.Event,
    ) -> str:
        episode_id = work["episode_id"]
        seed = work["seed"]
        effective_h = HClass.H2
        effective_k = KClass.K0
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

        initial_snapshot = self._store_state_snapshot(environment, state)
        if not work.get("resume"):
            self._writer.enqueue(
                UpdateEpisodeCommand(
                    episode_id=episode_id,
                    values={"initial_state_artifact_id": initial_snapshot},
                )
            )
        self._emit_episode_event(run_id, episode_id, "episode.started", {"seed": seed})
        self._record_assistance(
            run_id,
            effective_h,
            effective_k,
            declared_h=condition.protocol.declared_assistance,
            declared_k=condition.protocol.declared_knowledge,
        )

        if _state_is_terminal(state):
            self._writer.enqueue(
                FinalizeEpisodeCommand(
                    episode_id=episode_id,
                    episode_values={
                        "status": EpisodeState.COMPLETED.value,
                        "outcome": "completed",
                        "final_state_artifact_id": initial_snapshot,
                        "effective_assistance": _assistance_string(effective_h, effective_k),
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

        persistent_memory_items: tuple[Any, ...] = ()
        if (
            strategy.descriptor.declared_regime == "R7"
            and _search_memory_mode(condition) == "persistent"
        ):
            persistent_memory_items = self._load_persistent_search_memory(episode_id)

        single_player = self._single_player(condition)
        model_color = self._model_color(condition)
        opponent = self._opponent_for(condition)
        if opponent is None and not single_player:
            opponent = self._model_opponent_for(
                run_id=run_id,
                episode_id=episode_id,
                condition=condition,
                strategy=strategy,
                backend=recording_backend,
                environment=environment,
                observation_policy=observation_policy,
                artifact_store=self._artifact_store,
                writer=self._writer,
                event_sink=self._event_sink,
                declared_h=condition.protocol.declared_assistance,
                declared_k=condition.protocol.declared_knowledge,
                knowledge=knowledge,
            )
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
                    run_h, run_k = self._run_assistance.get(run_id, (effective_h, effective_k))
                    return await self._complete_episode(
                        run_id,
                        episode_id,
                        environment,
                        state,
                        ordinal,
                        "completed",
                        _assistance_string(run_h, run_k),
                        _assistance_violation(
                            condition.protocol.declared_assistance,
                            condition.protocol.declared_knowledge,
                            run_h,
                            run_k,
                        ),
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
                    knowledge=knowledge,
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
                    run_id,
                    episode_id,
                    environment,
                    state,
                    ordinal + 1,
                    "completed",
                    _assistance_string(effective_h, effective_k),
                    _assistance_violation(
                        condition.protocol.declared_assistance,
                        condition.protocol.declared_knowledge,
                        effective_h,
                        effective_k,
                    ),
                )

            search_workspace: Any = None
            search_memory: Any = None
            if strategy.descriptor.declared_regime in {"R6", "R7"}:
                from zugzwang_chess.environment.standard import StandardChessRulesKernel

                from ..search import SearchMemoryFabric, SearchWorkspace

                search_config_raw = condition.task.config.get("search")
                search_config = (
                    cast(dict[str, Any], search_config_raw)
                    if isinstance(search_config_raw, dict)
                    else {}
                )
                search_workspace = SearchWorkspace(
                    kernel=StandardChessRulesKernel(environment),
                    root_state=state,
                    max_nodes=int(search_config.get("max_nodes", 64)),
                    max_depth_plies=int(search_config.get("max_depth_plies", 6)),
                    max_validation_queries=int(search_config.get("max_validation_queries", 128)),
                    max_transition_queries=int(search_config.get("max_transition_queries", 64)),
                    session_id=str(new_id("ses")),
                )
                initial_items: tuple[Any, ...] = (
                    persistent_memory_items
                    if strategy.descriptor.declared_regime == "R7"
                    and _search_memory_mode(condition) == "persistent"
                    else ()
                )
                search_memory: Any = SearchMemoryFabric(
                    search_workspace,
                    initial_items=initial_items,
                )

            gateway = self._gateway_for(condition, environment)
            decision_capabilities = self._decision_capabilities(condition, strategy)
            bound_gateway = (
                gateway.bind(
                    state=state,
                    capabilities=decision_capabilities,
                    context=EventContext(run_id=run_id, episode_id=episode_id, step_id=step_id),
                )
                if gateway is not None
                else None
            )
            state_snapshot_ref = self._store_state_snapshot(environment, state)
            observation = environment.observe(state, observation_policy)
            observation_ref = store_json_artifact(
                cas=self._artifact_store,
                writer=self._writer,
                payload=observation_artifact_payload(
                    run_id=run_id,
                    episode_id=episode_id,
                    step_id=step_id,
                    state=state,
                    observation=cast(dict[str, Any], observation),
                    policy_settings=cast(dict[str, Any], dict(condition.protocol.observation)),
                    declared_h=condition.protocol.declared_assistance,
                    declared_k=condition.protocol.declared_knowledge,
                    state_ref=state_snapshot_ref,
                ),
                media_type="application/vnd.zugzwang.observation+json",
                redaction_policy="standard",
            ).as_id()
            self._writer.enqueue(
                UpdateStepCommand(
                    step_id=step_id,
                    values={"observation_artifact_id": observation_ref},
                )
            )
            self._emit_step_event(
                run_id,
                episode_id,
                step_id,
                "step.observation.created",
                {"state_fingerprint": _state_fingerprint(state)},
                artifact_refs=(observation_ref, state_snapshot_ref),
            )

            retry_feedback: str | None = None
            illegal_retries = 0
            decision_attempt_index = 0
            max_strategy_calls = max(1, strategy.descriptor.max_model_calls)
            decision_session: Any = None
            if getattr(strategy, "requires_decision_session", False):
                # The decision row references the step row: flush the queued
                # step/episode writes before opening the session, or the FK
                # fails against rows still sitting in the writer queue.
                await self._writer.flush()
                decision_session = self._open_cognitive_session(
                    run_id=run_id,
                    episode_id=episode_id,
                    step_id=step_id,
                    decision_ordinal=ordinal,
                    state=state,
                    strategy=strategy,
                    condition=condition,
                )
            while True:
                decision_context = DecisionContext(
                    run_id=run_id,
                    episode_id=episode_id,
                    step_id=step_id,
                    model=model,
                    backend=recording_backend,
                    tools={},
                    seed=seed,
                    config=_decision_config(condition, retry_feedback=retry_feedback),
                    artifact_store=self._artifact_store,
                    knowledge=knowledge,
                    state=state,
                    capabilities=decision_capabilities,
                    legality_gateway=bound_gateway,
                    search_workspace=search_workspace,
                    search_memory=search_memory,
                    decision_session=decision_session,
                )
                async with ledger_lock:
                    try:
                        ledger.check_limits_or_raise()
                        ledger.reserve("calls", max_strategy_calls)
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
                    recording_backend.begin_decision()
                    trace = await strategy.decide(observation, decision_context)
                except Exception as exc:
                    trace = None
                    decision_error = exc
                else:
                    decision_error = None
                logical_calls = max(1, len(trace.calls) if trace is not None else 0)
                async with ledger_lock:
                    ledger.reconcile("calls", max_strategy_calls, logical_calls)
                if trace is None:
                    from zugzwang_core.ports.strategy import DecisionTrace, Verdict

                    trace = DecisionTrace(
                        strategy_id=strategy.descriptor.strategy_id,
                        strategy_version=strategy.descriptor.strategy_version,
                        declared_regime=strategy.descriptor.declared_regime,
                        verdicts=(
                            Verdict(
                                kind="decision_error",
                                message=str(
                                    getattr(
                                        decision_error,
                                        "stable_code",
                                        decision_error or "unknown",
                                    )
                                )[:300],
                            ),
                        ),
                        final_action=None,
                        termination_reason="decision_error",
                    )
                effective_h, effective_k = _merge_assistance(
                    effective_h, effective_k, trace.assistance_impacts
                )
                if bound_gateway is not None:
                    effective_h, effective_k = _merge_assistance(
                        effective_h, effective_k, bound_gateway.assistance_impacts()
                    )
                self._record_assistance(
                    run_id,
                    effective_h,
                    effective_k,
                    declared_h=condition.protocol.declared_assistance,
                    declared_k=condition.protocol.declared_knowledge,
                )
                trace_ref = store_json_artifact(
                    cas=self._artifact_store,
                    writer=self._writer,
                    payload=decision_trace_payload(
                        run_id=run_id,
                        episode_id=episode_id,
                        step_id=step_id,
                        trace=trace,
                        attempt_index=decision_attempt_index,
                        gateway=bound_gateway,
                        attempt_evidence=recording_backend.evidence_for_current_decision(),
                    ),
                    media_type="application/vnd.zugzwang.decision-trace+json",
                    redaction_policy="standard",
                ).as_id()
                self._writer.enqueue(
                    UpdateStepCommand(
                        step_id=step_id,
                        values={"decision_trace_artifact_id": trace_ref},
                    )
                )
                self._emit_step_event(
                    run_id,
                    episode_id,
                    step_id,
                    "decision.trace.created",
                    {
                        "attempt_index": decision_attempt_index,
                        "strategy_id": trace.strategy_id,
                        "termination_reason": trace.termination_reason,
                    },
                    artifact_refs=(trace_ref,),
                    assistance=EventAssistance(
                        h=effective_h, k=effective_k, source="decision_trace"
                    ),
                )
                self._emit_step_event(
                    run_id,
                    episode_id,
                    step_id,
                    "step.decided",
                    {
                        "strategy_id": trace.strategy_id,
                        "strategy_version": trace.strategy_version,
                        "regime": trace.declared_regime,
                        "calls": len(trace.calls),
                        "termination_reason": trace.termination_reason,
                        "effective_assistance": _assistance_string(effective_h, effective_k),
                        "assistance_violated": _assistance_violation(
                            condition.protocol.declared_assistance,
                            condition.protocol.declared_knowledge,
                            effective_h,
                            effective_k,
                        ),
                    },
                    artifact_refs=(trace_ref,),
                    assistance=EventAssistance(h=effective_h, k=effective_k, source="decision"),
                )
                decision_attempt_index += 1

                legal_actions = environment.legal_actions(state)
                if trace.final_action is None:
                    provider_failure = decision_error is not None or any(
                        verdict.kind in {"provider_error", "decision_error"}
                        for verdict in trace.verdicts
                    )
                    if provider_failure:
                        # ZGW-0085/#13: provider failures are fail-closed. A
                        # timeout with unknown outcome may already have
                        # consumed provider work, so it must never re-enter
                        # the provider through the illegal-action retry
                        # budget; transport-level retries stay inside the
                        # recording backend under its own policy.
                        stable_code = (
                            str(getattr(decision_error, "stable_code", "decision_error"))
                            if decision_error is not None
                            else next(
                                (
                                    str(verdict.message) or "decision_error"
                                    for verdict in trace.verdicts
                                    if verdict.kind in {"provider_error", "decision_error"}
                                ),
                                "decision_error",
                            )
                        )[:128]
                        self._emit_step_event(
                            run_id,
                            episode_id,
                            step_id,
                            "step.decision_failed",
                            {"stable_code": stable_code},
                        )
                        self._persist_search_workspace(
                            workspace=search_workspace,
                            memory=search_memory,
                            run_id=run_id,
                            episode_id=episode_id,
                            step_id=step_id,
                            status="FAILED",
                            algorithm=_search_algorithm(strategy),
                        )
                        await self._fail_step(run_id, episode_id, step_id, "decision_error")
                        self._writer.enqueue(
                            FinalizeEpisodeCommand(
                                episode_id=episode_id,
                                episode_values={
                                    "status": EpisodeState.FAILED.value,
                                    "outcome": "decision_error",
                                },
                                envelope=self._episode_envelope(
                                    run_id,
                                    episode_id,
                                    "episode.failed",
                                    {"reason": "decision_error", "stable_code": stable_code},
                                ),
                            )
                        )
                        return "failed"
                    illegal_retries += 1
                    reason = trace.termination_reason if trace.termination_reason else "no_action"
                    self._emit_step_event(
                        run_id,
                        episode_id,
                        step_id,
                        "step.illegal_action_rejected",
                        {
                            "action": "(sem lance)",
                            "reason": reason,
                            "retry": illegal_retries,
                            "max_retries": condition.protocol.retries.illegal,
                            "legal_count": len(legal_actions.actions),
                        },
                        assistance=EventAssistance(
                            h=HClass.H1, k=KClass.K0, source="binary_legality"
                        ),
                    )
                    effective_h = max(effective_h, HClass.H1)
                    self._record_assistance(
                        run_id,
                        effective_h,
                        effective_k,
                        declared_h=condition.protocol.declared_assistance,
                        declared_k=condition.protocol.declared_knowledge,
                    )
                    if (
                        _retry_profile(condition) in {"no_retry", "parse_only"}
                        or illegal_retries > condition.protocol.retries.illegal
                    ):
                        self._persist_search_workspace(
                            workspace=search_workspace,
                            memory=search_memory,
                            run_id=run_id,
                            episode_id=episode_id,
                            step_id=step_id,
                            status="FAILED",
                            algorithm=_search_algorithm(strategy),
                        )
                        await self._fail_step(
                            run_id, episode_id, step_id, "illegal_action_retry_exhausted"
                        )
                        self._writer.enqueue(
                            FinalizeEpisodeCommand(
                                episode_id=episode_id,
                                episode_values={
                                    "status": EpisodeState.FAILED.value,
                                    "outcome": "failed",
                                },
                                envelope=self._episode_envelope(
                                    run_id,
                                    episode_id,
                                    "episode.failed",
                                    {
                                        "step": ordinal,
                                        "reason": "illegal_action_retry_exhausted",
                                        "illegal_attempts": illegal_retries,
                                    },
                                ),
                            )
                        )
                        return "failed"
                    retry_feedback = _illegal_retry_feedback(
                        "(sem lance)",
                        profile=_retry_profile(condition),
                        reason=reason,
                        legal_actions=legal_actions.actions,
                    )
                    continue

                final_action = trace.final_action
                try:
                    if isinstance(final_action, ActionHandle):
                        final_action = _resolve_handle(final_action, legal_actions)
                    elif isinstance(final_action, int):
                        final_action = _resolve_index(final_action, legal_actions)
                    action = _coerce_action(final_action, legal_actions)
                except Exception:
                    action = final_action
                if action not in legal_actions.actions:
                    illegal_retries += 1
                    retry_profile = _retry_profile(condition)
                    retry_h = HClass.H3 if retry_profile == "enumerate_after_failure" else HClass.H1
                    effective_h = max(effective_h, retry_h)
                    self._record_assistance(
                        run_id,
                        effective_h,
                        effective_k,
                        declared_h=condition.protocol.declared_assistance,
                        declared_k=condition.protocol.declared_knowledge,
                    )
                    self._emit_step_event(
                        run_id,
                        episode_id,
                        step_id,
                        "step.illegal_action_rejected",
                        {
                            "action": str(final_action)[:120],
                            "retry": illegal_retries,
                            "max_retries": condition.protocol.retries.illegal,
                            "legal_count": len(legal_actions.actions),
                        },
                        assistance=EventAssistance(
                            h=retry_h,
                            k=KClass.K0,
                            source=(
                                "enumerated_legality" if retry_h is HClass.H3 else "binary_legality"
                            ),
                        ),
                    )
                    if (
                        retry_profile in {"no_retry", "parse_only"}
                        or illegal_retries > condition.protocol.retries.illegal
                    ):
                        self._persist_search_workspace(
                            workspace=search_workspace,
                            memory=search_memory,
                            run_id=run_id,
                            episode_id=episode_id,
                            step_id=step_id,
                            status="FAILED",
                            algorithm=_search_algorithm(strategy),
                        )
                        await self._fail_step(
                            run_id, episode_id, step_id, "illegal_action_retry_exhausted"
                        )
                        self._writer.enqueue(
                            FinalizeEpisodeCommand(
                                episode_id=episode_id,
                                episode_values={
                                    "status": EpisodeState.FAILED.value,
                                    "outcome": "failed",
                                },
                                envelope=self._episode_envelope(
                                    run_id,
                                    episode_id,
                                    "episode.failed",
                                    {
                                        "step": ordinal,
                                        "reason": "illegal_action_retry_exhausted",
                                        "illegal_attempts": illegal_retries,
                                    },
                                ),
                            )
                        )
                        return "failed"
                    retry_feedback = _illegal_retry_feedback(
                        str(final_action),
                        profile=retry_profile,
                        reason="illegal_action",
                        legal_actions=legal_actions.actions,
                    )
                    continue
                break

            search_graph_ref: str | None = None
            if search_workspace is not None:
                search_graph_ref = self._persist_search_workspace(
                    workspace=search_workspace,
                    memory=search_memory,
                    run_id=run_id,
                    episode_id=episode_id,
                    step_id=step_id,
                    status="COMPLETED",
                    algorithm=_search_algorithm(strategy),
                )
                if (
                    strategy.descriptor.declared_regime == "R7"
                    and _search_memory_mode(condition) == "persistent"
                    and search_memory is not None
                ):
                    persistent_memory_items = search_memory.items

            transition = environment.transition(state, action)
            snapshot_ref = self._store_state_snapshot(environment, transition.state)

            committed_event = self._step_envelope(
                run_id,
                episode_id,
                step_id,
                "step.committed",
                {"action": str(action), "terminal": transition.terminal},
                artifact_refs=tuple(
                    ref for ref in (snapshot_ref, search_graph_ref) if ref is not None
                ),
            )
            checkpoint_row = {
                "run_id": run_id,
                "stream_type": "step",
                "stream_id": step_id,
                "sequence_committed": 1,
                "state_artifact_id": snapshot_ref,
                "schema_version": "zgw.event/v1alpha1",
                "created_at": to_iso_z(utc_now()),
            }
            self._writer.enqueue(
                CommitStepCommand(
                    step_id=step_id,
                    step_values={
                        "status": "COMMITTED",
                        "action_json": {"action": str(action)},
                        "transition_artifact_id": snapshot_ref,
                        "effective_assistance": _assistance_string(effective_h, effective_k),
                        "assistance_violated": 1
                        if _assistance_violation(
                            condition.protocol.declared_assistance,
                            condition.protocol.declared_knowledge,
                            effective_h,
                            effective_k,
                        )
                        else 0,
                        **(
                            {
                                "search_session_id": search_workspace.session_id,
                                "search_graph_artifact_id": search_graph_ref,
                            }
                            if search_workspace is not None and search_graph_ref is not None
                            else {}
                        ),
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
                    run_id,
                    episode_id,
                    environment,
                    state,
                    ordinal,
                    "completed",
                    _assistance_string(effective_h, effective_k),
                    _assistance_violation(
                        condition.protocol.declared_assistance,
                        condition.protocol.declared_knowledge,
                        effective_h,
                        effective_k,
                    ),
                )
            if self._is_episode_complete(environment, state, ordinal, max_steps):
                return await self._complete_episode(
                    run_id,
                    episode_id,
                    environment,
                    state,
                    ordinal,
                    "completed",
                    _assistance_string(effective_h, effective_k),
                    _assistance_violation(
                        condition.protocol.declared_assistance,
                        condition.protocol.declared_knowledge,
                        effective_h,
                        effective_k,
                    ),
                )

    def _store_state_snapshot(self, environment: Environment[Any, Any, Any], state: Any) -> str:
        return store_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=environment.snapshot(state),
        ).as_id()

    def _load_persistent_search_memory(self, episode_id: str) -> tuple[Any, ...]:
        """Reload the latest committed episode memory after a process restart."""
        from zugzwang_core.domain.artifacts import ArtifactRef

        from ..search import MemoryItem

        for row in reversed(self._steps.for_episode(episode_id)):
            if row.get("status") != "COMMITTED":
                continue
            graph_ref = row.get("search_graph_artifact_id")
            if not graph_ref:
                continue
            payload = self._artifact_store.get(ArtifactRef.parse(str(graph_ref)))
            try:
                data = json.loads(payload.data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            raw_items = data.get("memory")
            if not isinstance(raw_items, list):
                return ()
            items: list[MemoryItem] = []
            for raw in cast(list[Any], raw_items):
                if not isinstance(raw, dict):
                    continue
                raw_data = cast(dict[str, Any], raw)
                try:
                    items.append(
                        MemoryItem(
                            memory_id=str(raw_data["memory_id"]),
                            kind=str(raw_data["kind"]),
                            content=str(raw_data["content"]),
                            source_node_ids=tuple(
                                str(item) for item in cast(list[Any], raw_data["source_node_ids"])
                            ),
                            generated_by=str(raw_data["generated_by"]),
                            created_at_index=int(raw_data["created_at_index"]),
                            source_position_keys=tuple(
                                str(item)
                                for item in cast(
                                    list[Any], raw_data.get("source_position_keys", ())
                                )
                            ),
                        )
                    )
                except Exception:
                    continue
            return tuple(items)
        return ()

    def _persist_search_workspace(
        self,
        *,
        workspace: Any,
        memory: Any,
        run_id: str,
        episode_id: str,
        step_id: str,
        status: str,
        algorithm: str = "R6-BatchedTree",
    ) -> str | None:
        if workspace is None:
            return None
        from ..search import persist_workspace

        graph_ref = persist_workspace(
            workspace=workspace,
            writer=self._writer,
            cas=self._artifact_store,
            run_id=run_id,
            episode_id=episode_id,
            step_id=step_id,
            algorithm=algorithm,
            memory=memory,
            status=status,
            event_sink=self._event_sink,
        )
        self._writer.enqueue(
            UpdateStepCommand(
                step_id=step_id,
                values={
                    "search_session_id": workspace.session_id,
                    "search_graph_artifact_id": graph_ref,
                },
            )
        )
        self._emit_step_event(
            run_id,
            episode_id,
            step_id,
            "search.session.completed",
            {"search_session_id": workspace.session_id, "status": status},
            artifact_refs=(graph_ref,),
            assistance=EventAssistance(h=HClass.H4, k=KClass.K0, source="model_only_search"),
        )
        return graph_ref

    def _gateway_for(
        self, condition: ResolvedCondition, environment: Environment[Any, Any, Any]
    ) -> LegalityGateway | None:
        if condition.task.plugin != "chess.tasks":
            return None
        from zugzwang_chess.environment.standard import StandardChessRulesKernel

        config = condition.protocol.legality
        legal_settings = condition.protocol.observation.get("legal_actions")
        if isinstance(legal_settings, dict) and legal_settings.get("exposure") == "delayed":
            # Delayed enumeration is explicit protocol exposure.  It is not
            # inserted into the initial observation; the strategy requests it
            # only after its free-reasoning phase.
            config = config.model_copy(update={"enumerate": {"enabled": True}})
        return LegalityGateway(
            kernel=StandardChessRulesKernel(environment),
            config=config,
            event_sink=self._event_sink,
        )

    @staticmethod
    def _decision_capabilities(
        condition: ResolvedCondition, strategy: DecisionStrategy
    ) -> DecisionCapabilities:
        legal_settings = condition.protocol.observation.get("legal_actions")
        exposure = legal_settings.get("exposure") if isinstance(legal_settings, dict) else None
        descriptor = strategy.descriptor
        if exposure == "delayed" and descriptor.consumes_legal_actions:
            return DecisionCapabilities(
                validate_action=True,
                enumerate_actions=True,
                transition_sandbox=condition.protocol.legality.transition_sandbox,
                query_terminal=condition.protocol.legality.transition_sandbox,
                validation_feedback=condition.protocol.legality.validation_feedback,
            )
        if descriptor.declared_regime.startswith("R6"):
            return DecisionCapabilities(
                validate_action=condition.protocol.legality.validation.enabled,
                enumerate_actions=condition.protocol.legality.enumerate.enabled,
                transition_sandbox=condition.protocol.legality.transition_sandbox,
                query_terminal=condition.protocol.legality.transition_sandbox,
                validation_feedback=condition.protocol.legality.validation_feedback,
            )
        return DecisionCapabilities()

    def _record_assistance(
        self,
        run_id: str,
        h: HClass,
        k: KClass,
        *,
        declared_h: str | None = None,
        declared_k: str | None = None,
    ) -> None:
        current_h, current_k = self._run_assistance.get(run_id, (HClass.H0, KClass.K0))
        self._run_assistance[run_id] = (max(current_h, h), max(current_k, k))
        if declared_h is not None and (
            h > HClass[declared_h] or (declared_k is not None and k > KClass[declared_k])
        ):
            self._run_assistance_violated[run_id] = True

    def _max_steps_for(self, condition: ResolvedCondition, task_kind: str) -> int | None:
        from ..coercions import as_int

        if task_kind == "full-game":
            if "max_plies" in condition.task.config and condition.task.config["max_plies"] is None:
                return None
            return as_int(condition.task.config.get("max_plies"), 240)
        if task_kind in {"move-selection", "state-reconstruction"}:
            return 1
        return as_int(condition.task.config.get("max_steps"), 10)

    def _is_episode_complete(
        self,
        environment: Environment[Any, Any, Any],
        state: Any,
        ordinal: int,
        max_steps: int | None,
    ) -> bool:
        if _state_is_terminal(state):
            return True
        return max_steps is not None and ordinal >= max_steps

    async def _complete_episode(
        self,
        run_id: str,
        episode_id: str,
        environment: Environment[Any, Any, Any],
        state: Any,
        ordinal: int,
        outcome: str,
        effective_assistance: str = "H2",
        assistance_violated: bool = False,
    ) -> str:
        snapshot_ref = self._store_state_snapshot(environment, state)
        self._writer.enqueue(
            FinalizeEpisodeCommand(
                episode_id=episode_id,
                episode_values={
                    "status": EpisodeState.COMPLETED.value,
                    "outcome": outcome,
                    "final_state_artifact_id": snapshot_ref,
                    "effective_assistance": effective_assistance,
                    "assistance_violated": 1 if assistance_violated else 0,
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
        prepare_step = getattr(opponent, "prepare_step", None)
        if callable(prepare_step):
            prepare_step(step_id)
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
        snapshot_ref = self._store_state_snapshot(environment, transition.state)
        metadata_raw: Any = getattr(opponent, "metadata", {})
        if callable(metadata_raw):
            metadata_raw = metadata_raw()
        policy_metadata: dict[str, Any] = (
            cast(dict[str, Any], metadata_raw) if isinstance(metadata_raw, dict) else {}
        )
        effective_raw = str(policy_metadata.get("effective_assistance", "H2/K0"))
        effective_parts = effective_raw.split("/", 1)
        opponent_h = (
            HClass[effective_parts[0]] if effective_parts[0] in HClass.__members__ else HClass.H2
        )
        opponent_k = (
            KClass[effective_parts[1]]
            if len(effective_parts) > 1 and effective_parts[1] in KClass.__members__
            else KClass.K0
        )
        self._record_assistance(
            run_id,
            opponent_h,
            opponent_k,
            declared_h=condition.protocol.declared_assistance,
            declared_k=condition.protocol.declared_knowledge,
        )
        action_json: dict[str, Any] = {"action": str(action)}
        if policy_metadata:
            action_json["policy"] = policy_metadata
        self._writer.enqueue(
            CommitStepCommand(
                step_id=step_id,
                step_values={
                    "status": "COMMITTED",
                    "action_json": action_json,
                    "transition_artifact_id": snapshot_ref,
                    "effective_assistance": _assistance_string(opponent_h, opponent_k),
                    "assistance_violated": 1
                    if _assistance_violation(
                        condition.protocol.declared_assistance,
                        condition.protocol.declared_knowledge,
                        opponent_h,
                        opponent_k,
                    )
                    else 0,
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
                        "action": str(action),
                        "terminal": transition.terminal,
                        "policy": policy_metadata,
                    },
                    artifact_refs=(snapshot_ref,),
                    assistance=EventAssistance(h=opponent_h, k=opponent_k, source="model_opponent"),
                ),
                checkpoint_row={
                    "run_id": run_id,
                    "stream_type": "step",
                    "stream_id": step_id,
                    "sequence_committed": 1,
                    "state_artifact_id": snapshot_ref,
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
        knowledge: tuple[Any, ...],
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
            config=_decision_config(condition),
            artifact_store=self._artifact_store,
            knowledge=knowledge,
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
        snapshot_ref = store_artifact(
            cas=self._artifact_store,
            writer=self._writer,
            payload=canonical,
        ).as_id()
        self._writer.enqueue(
            CommitStepCommand(
                step_id=step_id,
                step_values={
                    "status": "COMMITTED",
                    "action_json": {"action": predicted, "kind": "fen_prediction"},
                    "transition_artifact_id": snapshot_ref,
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
                    artifact_refs=(snapshot_ref,),
                ),
                checkpoint_row={
                    "run_id": run_id,
                    "stream_type": "step",
                    "stream_id": step_id,
                    "sequence_committed": 1,
                    "state_artifact_id": snapshot_ref,
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
        self,
        run_id: str,
        episode_id: str,
        step_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        artifact_refs: tuple[str, ...] = (),
        assistance: EventAssistance | None = None,
    ) -> None:
        self._event_sink.append(
            self._step_envelope(
                run_id,
                episode_id,
                step_id,
                event_type,
                payload,
                artifact_refs=artifact_refs,
                assistance=assistance,
            )
        )

    def _step_envelope(
        self,
        run_id: str,
        episode_id: str,
        step_id: str,
        event_type: str,
        payload: dict[str, Any],
        artifact_refs: tuple[str, ...] = (),
        assistance: EventAssistance | None = None,
    ) -> EventEnvelope:
        return EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="step",
            stream_id=step_id,
            sequence=0,
            context=EventContext(run_id=run_id, episode_id=episode_id, step_id=step_id),
            artifact_refs=artifact_refs,
            assistance=assistance,
        )

    def _environment_for(self, condition: ResolvedCondition) -> Environment[Any, Any, Any]:
        if condition.task.plugin in {"fake.counter", "chess.tasks"}:
            if condition.task.plugin == "fake.counter":
                from ..fakes import CounterEnvironment

                return CounterEnvironment()
            from zugzwang_chess import StandardChessEnvironment

            return StandardChessEnvironment()
        raise ValueError(f"no environment for task {condition.task.plugin!r}")

    def _open_cognitive_session(
        self,
        *,
        run_id: str,
        episode_id: str,
        step_id: str,
        decision_ordinal: int,
        state: Any,
        strategy: DecisionStrategy,
        condition: ResolvedCondition,
    ) -> Any:
        """Open one CognitiveBoard decision session for a step (§26.1).

        The composition root injects the factory; the coordinator itself
        stays free of SQL/CAS wiring. Without a factory, a cognitive strategy
        cannot run — an explicit error instead of a silent degraded path.
        """
        if self._cognitive_session_factory is None:
            raise ValueError(
                f"strategy {getattr(strategy, 'strategy_id', '?')!r} requires a "
                "cognitive session factory (DurableRunServices provides one)"
            )
        raw_mode = condition.task.config.get("cognitive_interaction_mode", "native_tools")
        interaction_mode = (
            str(raw_mode) if raw_mode in {"native_tools", "json_commands"} else "native_tools"
        )
        return self._cognitive_session_factory(
            run_id=run_id,
            episode_id=episode_id,
            step_id=step_id,
            decision_ordinal=decision_ordinal,
            state=state,
            strategy=strategy,
            interaction_mode=interaction_mode,
        )

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
                if player.model.strategy == "chess.reason_then_ground":
                    from zugzwang_chess.strategies.reason_then_ground import (
                        ReasonThenGroundStrategy,
                    )

                    return ReasonThenGroundStrategy()
                if player.model.strategy == "chess.reconstruct":
                    from zugzwang_chess.strategies.reconstruct import ReconstructStrategy

                    return ReconstructStrategy()
                if player.model.strategy == "chess.r6_batched_tree":
                    from zugzwang_chess.strategies.batched_tree import BatchedTreeStrategy

                    search_config = condition.task.config.get("search")
                    config = (
                        cast(dict[str, Any], search_config)
                        if isinstance(search_config, dict)
                        else {}
                    )
                    return BatchedTreeStrategy(
                        initial_candidates=int(config.get("initial_candidates", 4)),
                        judges=int(config.get("judges", 3)),
                    )
                if player.model.strategy == "chess.cognitive_navigation":
                    from ..cognition.navigation import CognitiveNavigationStrategy

                    return CognitiveNavigationStrategy()
                if player.model.strategy == "chess.multi_agent_review":
                    from zugzwang_chess.strategies.multi_agent_review import (
                        MultiAgentReviewStrategy,
                    )

                    return MultiAgentReviewStrategy()
                if player.model.strategy == "chess.legal_tree_memory":
                    from zugzwang_chess.strategies.legal_tree_memory import (
                        LegalTreeMemoryStrategy,
                    )

                    search_config = condition.task.config.get("search")
                    config = (
                        cast(dict[str, Any], search_config)
                        if isinstance(search_config, dict)
                        else {}
                    )
                    return LegalTreeMemoryStrategy(
                        memory_mode=str(config.get("memory_mode", "episodic")),
                    )
                if player.model.strategy == "chess.single_agent_tree":
                    from zugzwang_chess.strategies.single_agent_tree import (
                        SingleAgentTreeStrategy,
                    )

                    search_config = condition.task.config.get("search")
                    config = (
                        cast(dict[str, Any], search_config)
                        if isinstance(search_config, dict)
                        else {}
                    )
                    return SingleAgentTreeStrategy(
                        memory_mode=str(config.get("memory_mode", "episodic")),
                    )
                if player.model.strategy == "chess.structured":
                    from zugzwang_chess.strategies.structured import StructuredStrategy

                    return StructuredStrategy()
                if player.model.strategy == "chess.repair":
                    from zugzwang_chess.strategies.repair import RepairStrategy

                    return RepairStrategy(
                        max_retries=condition.protocol.retries.parse,
                        feedback=condition.protocol.retries.feedback,
                        retry_profile=_retry_profile(condition),
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
                if plugin == "chess.stockfish":
                    from zgw_eval_stockfish.opponent import StockfishOpponent

                    config = player.policy.config
                    executable_raw = config.get("executable", "stockfish")
                    if not isinstance(executable_raw, str) or not executable_raw:
                        raise ValueError("chess.stockfish requires a non-empty executable")
                    elo_raw = config.get("elo")
                    if elo_raw is not None and (
                        isinstance(elo_raw, bool) or not isinstance(elo_raw, int)
                    ):
                        raise ValueError("chess.stockfish elo must be an integer")
                    limit_raw = config.get("limit")
                    limit: dict[str, int] | None = None
                    if limit_raw is not None:
                        if not isinstance(limit_raw, dict):
                            raise ValueError("chess.stockfish limit must be a mapping")
                        limit = {}
                        for key, value in limit_raw.items():
                            if isinstance(value, bool) or not isinstance(value, int):
                                raise ValueError("chess.stockfish limits must be integers")
                            limit[str(key)] = value
                    options_raw = config.get("options")
                    options: dict[str, str] | None = None
                    if options_raw is not None:
                        if not isinstance(options_raw, dict):
                            raise ValueError("chess.stockfish options must be a mapping")
                        options = {str(key): str(value) for key, value in options_raw.items()}
                    approximate_raw = config.get("allow_approximate", False)
                    if not isinstance(approximate_raw, bool):
                        raise ValueError("chess.stockfish allow_approximate must be a boolean")
                    return StockfishOpponent(
                        executable_raw,
                        elo=elo_raw,
                        limit=limit,
                        options=options,
                        allow_approximate=approximate_raw,
                    )
                if plugin == "fake.stay":
                    return None
        return None

    def _model_opponent_for(
        self,
        *,
        run_id: str,
        episode_id: str,
        condition: ResolvedCondition,
        strategy: DecisionStrategy,
        backend: Any,
        environment: Environment[Any, Any, Any],
        observation_policy: ObservationPolicy,
        artifact_store: ContentAddressedStore,
        writer: PersistenceWriter,
        event_sink: PersistentEventSink,
        declared_h: str,
        declared_k: str,
        knowledge: tuple[Any, ...],
    ) -> Any | None:
        model_players = [
            player.model for player in condition.players.values() if player.model is not None
        ]
        if len(model_players) != 2:
            return None
        first, second = model_players
        first_identity = (first.backend, first.provider, first.model, first.strategy)
        second_identity = (second.backend, second.provider, second.model, second.strategy)
        if first_identity != second_identity:
            raise ValueError(
                "self-play currently requires identical model/backend/strategy on both sides"
            )
        return _ModelOpponent(
            run_id=run_id,
            episode_id=episode_id,
            model=ModelRef(
                backend=second.backend or "fake.backend",
                provider=second.provider or "fake",
                model=second.model or "scripted",
            ),
            strategy=strategy,
            backend=backend,
            environment=environment,
            observation_policy=observation_policy,
            artifact_store=artifact_store,
            writer=writer,
            event_sink=event_sink,
            declared_h=declared_h,
            declared_k=declared_k,
            knowledge=knowledge,
            config=_decision_config(condition),
        )

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


def _resolve_handle(handle: ActionHandle, legal_actions: Any) -> Any:
    if handle.ordering_hash and handle.ordering_hash != legal_actions.legal_hash:
        raise ValueError("opaque action handle belongs to a different legal ordering")
    return _resolve_index(handle.index, legal_actions)


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


def _decision_config(
    condition: ResolvedCondition, *, retry_feedback: str | None = None
) -> dict[str, Any]:
    """Protocol prompt overrides become strategy context config (persona/few-shot)."""
    prompt_spec = condition.protocol.prompt
    config: dict[str, Any] = {
        "prompt": {
            "system_instructions": prompt_spec.system_instructions,
            "examples": [dict(example) for example in prompt_spec.examples],
        }
    }
    config["retry_profile"] = _retry_profile(condition)
    legal_settings = condition.protocol.observation.get("legal_actions")
    if isinstance(legal_settings, dict):
        config["legality"] = {
            "encoding": str(legal_settings.get("encoding", "uci")),
        }
    search_config = condition.task.config.get("search")
    if isinstance(search_config, dict):
        config["search"] = dict(search_config)
    cognitive_config = condition.task.config.get("cognitive")
    if isinstance(cognitive_config, dict):
        # Operator directive for the cognitive loop (directed pilot tests):
        # journaled in the request artifact, never a scripted move sequence.
        config["cognitive"] = dict(cognitive_config)
    if retry_feedback:
        config["retry_feedback"] = retry_feedback
    return config


def _search_memory_mode(condition: ResolvedCondition) -> str:
    search_config = condition.task.config.get("search")
    if isinstance(search_config, dict):
        mode = str(search_config.get("memory_mode", "episodic"))
        if mode in {"episodic", "persistent"}:
            return mode
    return "episodic"


def _search_algorithm(strategy: DecisionStrategy) -> str:
    if strategy.descriptor.strategy_id == "chess.single_agent_tree":
        return "R7-SingleAgentTree"
    if strategy.descriptor.declared_regime == "R7":
        return "R7-LegalTreeMemory"
    return "R6-BatchedTree"


def _retry_profile(condition: ResolvedCondition) -> str:
    explicit = condition.protocol.retry_profile or condition.protocol.retries.retry_profile
    if explicit:
        return explicit
    if condition.protocol.retries.illegal <= 0:
        return "no_retry"
    legacy = condition.protocol.retries.feedback
    if legacy in {"legality_only", "binary"}:
        return "binary_legality"
    if legacy in {"reason_category", "legality_reason"}:
        return "legality_reason"
    if legacy in {"enumerated", "constrained", "legal_actions"}:
        return "enumerate_after_failure"
    return "binary_legality"


def _illegal_retry_feedback(
    action: str,
    *,
    profile: str,
    reason: str,
    legal_actions: tuple[Any, ...],
) -> str:
    """Project formal failure into the explicitly selected retry profile."""
    prefix = (
        f"Your previous move {action[:80]!r} was rejected as illegal. "
        "Choose another move for the same position. "
    )
    if profile == "enumerate_after_failure":
        legal = ", ".join(str(candidate) for candidate in legal_actions)
        return f"{prefix}Legal moves: {legal}. Reply with one move only."
    if profile == "legality_reason":
        return f"{prefix}Formal reason: {reason}. Reply with one move only."
    # Binary feedback intentionally has no legal count, list, ranking or
    # candidate hint.  The model has to generate the repair itself.
    return f"{prefix}The formal result was ILLEGAL. Reply with one move only."


def _merge_assistance(
    current_h: HClass,
    current_k: KClass,
    impacts: tuple[Any, ...] | list[Any],
) -> tuple[HClass, KClass]:
    h = current_h
    k = current_k
    for impact in impacts:
        h = max(h, impact.h)
        k = max(k, impact.k)
    return h, k


def _assistance_string(h: HClass, k: KClass) -> str:
    return f"{h.name}/{k.name}"


def _assistance_violation(
    declared_h: str,
    declared_k: str,
    effective_h: HClass,
    effective_k: KClass,
) -> bool:
    return effective_h > HClass[declared_h] or effective_k > KClass[declared_k]


def _state_fingerprint(state: Any) -> str | None:
    value = getattr(state, "fingerprint", None)
    if callable(value):
        return str(value())
    return str(value) if value else None
