"""Fake plugins for offline development and testing (design §24.2)."""

from .fake_backend import DeterministicModelBackend, FakeBackendRule
from .fake_environment import CounterEnvironment, CounterState
from .fake_evaluator import FakeEvaluator
from .fake_strategy import FakeDirectStrategy
from .registry_entries import (
    FAKE_BACKEND_ENTRY,
    FAKE_ENVIRONMENT_ENTRY,
    FAKE_EVALUATOR_ENTRY,
    FAKE_STRATEGY_ENTRY,
    FAKE_TASK_ENTRY,
)

__all__ = [
    "FAKE_BACKEND_ENTRY",
    "FAKE_ENVIRONMENT_ENTRY",
    "FAKE_EVALUATOR_ENTRY",
    "FAKE_STRATEGY_ENTRY",
    "FAKE_TASK_ENTRY",
    "CounterEnvironment",
    "CounterState",
    "DeterministicModelBackend",
    "FakeBackendRule",
    "FakeDirectStrategy",
    "FakeEvaluator",
]
