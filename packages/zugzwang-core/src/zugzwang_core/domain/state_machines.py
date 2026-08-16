"""Pure state machines for run, episode and step (design §10.3 and §10.4).

Transitions not listed here are rejected by the domain layer. The critical
boundary is ``COMMITTED``: after it, resume never repeats the model call nor
re-applies the action.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from .errors import StateTransitionError


class RunState(StrEnum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PAUSING = "PAUSING"
    PAUSED = "PAUSED"
    INTERRUPTED = "INTERRUPTED"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


RUN_TRANSITIONS: Mapping[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.VALIDATED}),
    RunState.VALIDATED: frozenset({RunState.PLANNED, RunState.FAILED}),
    RunState.PLANNED: frozenset({RunState.RUNNING}),
    RunState.RUNNING: frozenset(
        {
            RunState.PAUSING,
            RunState.INTERRUPTED,
            RunState.FINALIZING,
            RunState.FAILED,
            RunState.CANCELED,
        }
    ),
    RunState.PAUSING: frozenset({RunState.PAUSED}),
    RunState.PAUSED: frozenset({RunState.RUNNING, RunState.CANCELED}),
    RunState.INTERRUPTED: frozenset({RunState.RUNNING, RunState.CANCELED}),
    RunState.FINALIZING: frozenset({RunState.COMPLETED, RunState.FAILED}),
    RunState.COMPLETED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELED: frozenset(),
}

RUN_TERMINAL_STATES: frozenset[RunState] = frozenset(
    {RunState.COMPLETED, RunState.FAILED, RunState.CANCELED}
)


class EpisodeState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    INTERRUPTED = "INTERRUPTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


EPISODE_TRANSITIONS: Mapping[EpisodeState, frozenset[EpisodeState]] = {
    EpisodeState.PENDING: frozenset({EpisodeState.RUNNING, EpisodeState.CANCELED}),
    EpisodeState.RUNNING: frozenset(
        {
            EpisodeState.INTERRUPTED,
            EpisodeState.COMPLETED,
            EpisodeState.FAILED,
            EpisodeState.CANCELED,
        }
    ),
    EpisodeState.INTERRUPTED: frozenset({EpisodeState.RUNNING, EpisodeState.CANCELED}),
    EpisodeState.COMPLETED: frozenset(),
    EpisodeState.FAILED: frozenset(),
    EpisodeState.CANCELED: frozenset(),
}

EPISODE_TERMINAL_STATES: frozenset[EpisodeState] = frozenset(
    {EpisodeState.COMPLETED, EpisodeState.FAILED, EpisodeState.CANCELED}
)


class StepState(StrEnum):
    PENDING = "PENDING"
    OBSERVING = "OBSERVING"
    DECIDING = "DECIDING"
    VERIFYING = "VERIFYING"
    APPLYING = "APPLYING"
    COMMITTED = "COMMITTED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    CANCELED = "CANCELED"


STEP_TRANSITIONS: Mapping[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset(
        {StepState.OBSERVING, StepState.TERMINAL_FAILURE, StepState.CANCELED}
    ),
    StepState.OBSERVING: frozenset(
        {StepState.DECIDING, StepState.TERMINAL_FAILURE, StepState.CANCELED}
    ),
    StepState.DECIDING: frozenset(
        {
            StepState.VERIFYING,
            StepState.RETRYABLE_FAILURE,
            StepState.TERMINAL_FAILURE,
            StepState.CANCELED,
        }
    ),
    StepState.VERIFYING: frozenset(
        {
            StepState.APPLYING,
            StepState.RETRYABLE_FAILURE,
            StepState.TERMINAL_FAILURE,
            StepState.CANCELED,
        }
    ),
    StepState.APPLYING: frozenset(
        {StepState.COMMITTED, StepState.TERMINAL_FAILURE, StepState.CANCELED}
    ),
    StepState.COMMITTED: frozenset(),
    StepState.RETRYABLE_FAILURE: frozenset(
        {
            StepState.OBSERVING,
            StepState.DECIDING,
            StepState.VERIFYING,
            StepState.TERMINAL_FAILURE,
            StepState.CANCELED,
        }
    ),
    StepState.TERMINAL_FAILURE: frozenset(),
    StepState.CANCELED: frozenset(),
}

STEP_TERMINAL_STATES: frozenset[StepState] = frozenset(
    {StepState.COMMITTED, StepState.TERMINAL_FAILURE, StepState.CANCELED}
)


def can_transition(current: RunState | EpisodeState | StepState, target: object) -> bool:
    if isinstance(current, RunState):
        return target in RUN_TRANSITIONS[current]
    if isinstance(current, EpisodeState):
        return target in EPISODE_TRANSITIONS[current]
    return target in STEP_TRANSITIONS[current]


def require_transition(current: RunState | EpisodeState | StepState, target: object) -> None:
    if not can_transition(current, target):
        raise StateTransitionError(
            f"invalid transition {current.value} -> {getattr(target, 'value', target)}"
        )
