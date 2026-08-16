"""Unit tests: identifiers, clocks, money, seeds, state machines."""

from __future__ import annotations

import itertools

import pytest

from zugzwang_core.domain.budgets import BudgetLedger, BudgetSpec
from zugzwang_core.domain.clocks import from_iso_z, to_iso_z, utc_now
from zugzwang_core.domain.errors import BudgetExceededError, InvariantError, StateTransitionError
from zugzwang_core.domain.ids import Id, new_id
from zugzwang_core.domain.money import (
    CostEntry,
    CostStatus,
    Money,
    TokenUsage,
    UsageSource,
)
from zugzwang_core.domain.seeds import derive_seed, derive_step_seed
from zugzwang_core.domain.state_machines import (
    EpisodeState,
    RunState,
    StepState,
    can_transition,
    require_transition,
)


@pytest.mark.unit
class TestIds:
    def test_new_id_has_prefix(self) -> None:
        run_id = new_id("run")
        assert run_id.value.startswith("run_")
        assert len(run_id.value) == 26

    def test_parse_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            Id("not-an-id")
        with pytest.raises(ValueError):
            Id("run_short")

    def test_ids_are_unique(self) -> None:
        assert new_id("evt") != new_id("evt")


@pytest.mark.unit
class TestClocks:
    def test_roundtrip_iso_z(self) -> None:
        now = utc_now()
        assert from_iso_z(to_iso_z(now)) == now.replace(microsecond=now.microsecond // 1000 * 1000)

    def test_to_iso_z_has_z_suffix(self) -> None:
        assert to_iso_z(utc_now()).endswith("Z")


@pytest.mark.unit
class TestMoney:
    def test_money_add(self) -> None:
        assert Money("1.5") + Money("2.25") == Money("3.75")

    def test_money_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            Money("-1")

    def test_unknown_cost_never_zero(self) -> None:
        unknown = CostEntry(None, CostStatus.UNKNOWN)
        known = CostEntry(Money("1.0"), CostStatus.PROVIDER_REPORTED)
        assert (unknown + known).amount is None
        assert (unknown + known).status is CostStatus.UNKNOWN

    def test_usage_source_merge(self) -> None:
        provider = TokenUsage(1, 2, UsageSource.PROVIDER)
        estimated = TokenUsage(3, 4, UsageSource.ESTIMATED)
        merged = provider + estimated
        assert merged.source is UsageSource.PROVIDER
        assert merged.total_tokens == 10


@pytest.mark.unit
class TestSeeds:
    def test_seed_derivation_is_deterministic(self) -> None:
        assert derive_seed(42, 0, 0) == derive_seed(42, 0, 0)

    def test_seed_derivation_distinguishes_indices(self) -> None:
        seeds = {derive_seed(42, c, e) for c in range(4) for e in range(4)}
        assert len(seeds) == 16

    def test_step_seed(self) -> None:
        assert derive_step_seed(100, 0) != derive_step_seed(100, 1)


@pytest.mark.unit
class TestStateMachines:
    def test_run_flow_valid(self) -> None:
        chain = (
            RunState.CREATED,
            RunState.VALIDATED,
            RunState.PLANNED,
            RunState.RUNNING,
            RunState.FINALIZING,
            RunState.COMPLETED,
        )
        for current, target in itertools.pairwise(chain):
            require_transition(current, target)
        assert can_transition(RunState.RUNNING, RunState.INTERRUPTED)
        assert can_transition(RunState.INTERRUPTED, RunState.RUNNING)

    def test_terminal_states_accept_nothing(self) -> None:
        assert not can_transition(RunState.COMPLETED, RunState.RUNNING)
        assert not can_transition(RunState.FAILED, RunState.RUNNING)
        assert not can_transition(RunState.CANCELED, RunState.RUNNING)

    def test_invalid_transition_raises(self) -> None:
        with pytest.raises(StateTransitionError):
            require_transition(RunState.CREATED, RunState.RUNNING)

    def test_step_committed_is_terminal(self) -> None:
        assert not can_transition(StepState.COMMITTED, StepState.DECIDING)
        assert can_transition(StepState.DECIDING, StepState.RETRYABLE_FAILURE)
        assert can_transition(StepState.RETRYABLE_FAILURE, StepState.DECIDING)

    def test_episode_machine(self) -> None:
        assert can_transition(EpisodeState.PENDING, EpisodeState.RUNNING)
        assert can_transition(EpisodeState.INTERRUPTED, EpisodeState.RUNNING)


@pytest.mark.unit
class TestBudgets:
    def test_reserve_and_reconcile(self) -> None:
        ledger = BudgetLedger(BudgetSpec(max_calls=2))
        ledger.reserve("calls", 1)
        ledger.reconcile("calls", 1, 1)
        assert ledger.used("calls") == 1
        assert ledger.remaining("calls") == 1

    def test_exceeded_raises(self) -> None:
        ledger = BudgetLedger(BudgetSpec(max_calls=1))
        ledger.reserve("calls", 1)
        with pytest.raises(BudgetExceededError):
            ledger.reserve("calls", 1)

    def test_underflow_raises(self) -> None:
        ledger = BudgetLedger(BudgetSpec(max_calls=5))
        with pytest.raises(InvariantError):
            ledger.reconcile("calls", 1, 1)

    def test_unlimited(self) -> None:
        ledger = BudgetLedger(BudgetSpec.unlimited())
        assert ledger.remaining("calls") is None
