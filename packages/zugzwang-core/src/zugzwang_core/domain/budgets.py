"""Budget specification and ledger (design §10.8).

Before a call the ledger reserves a conservative estimate; after the response
it reconciles real usage. If usage is missing it stays ``estimated`` — never
falsely ``actual`` (design §10.8).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from .errors import BudgetExceededError, InvariantError
from .money import CostEntry, Money, TokenUsage, decimal_from_any

BudgetUnit = Literal[
    "calls",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "usd",
    "wall_time_seconds",
    "failed_calls",
]


@dataclass(frozen=True, slots=True)
class BudgetSpec:
    """Declared limits. ``None`` means unlimited."""

    max_calls: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_usd: Decimal | None = None
    max_wall_time_seconds: float | None = None
    max_failed_calls: int | None = None
    max_concurrent_episodes: int = 1

    max_attempts_per_step: int = 1
    max_model_calls_per_step: int = 1
    max_tool_calls_per_step: int = 0
    max_output_tokens_per_step: int | None = None
    per_call_timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_calls",
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
            "max_failed_calls",
            "max_attempts_per_step",
            "max_model_calls_per_step",
            "max_tool_calls_per_step",
            "max_output_tokens_per_step",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.max_usd is not None and self.max_usd < 0:
            raise ValueError("max_usd must be non-negative")
        if self.max_concurrent_episodes < 1:
            raise ValueError("max_concurrent_episodes must be >= 1")

    @classmethod
    def unlimited(cls) -> BudgetSpec:
        return cls()


@dataclass(slots=True)
class Reservation:
    """A conservative reservation against the ledger."""

    unit: BudgetUnit
    amount: Decimal


@dataclass(slots=True)
class BudgetLedger:
    """In-memory budget ledger with reserve/reconcile semantics."""

    spec: BudgetSpec
    started_monotonic: float = field(default_factory=time.monotonic)

    _used: dict[BudgetUnit, Decimal] = field(
        default_factory=lambda: {
            "calls": Decimal(0),
            "input_tokens": Decimal(0),
            "output_tokens": Decimal(0),
            "total_tokens": Decimal(0),
            "usd": Decimal(0),
            "wall_time_seconds": Decimal(0),
            "failed_calls": Decimal(0),
        }
    )
    _reserved: dict[BudgetUnit, Decimal] = field(
        default_factory=lambda: {
            "calls": Decimal(0),
            "input_tokens": Decimal(0),
            "output_tokens": Decimal(0),
            "total_tokens": Decimal(0),
            "usd": Decimal(0),
            "wall_time_seconds": Decimal(0),
            "failed_calls": Decimal(0),
        }
    )

    def _limit(self, unit: BudgetUnit) -> Decimal | None:
        mapping = {
            "calls": self.spec.max_calls,
            "input_tokens": self.spec.max_input_tokens,
            "output_tokens": self.spec.max_output_tokens,
            "total_tokens": self.spec.max_total_tokens,
            "usd": self.spec.max_usd,
            "wall_time_seconds": self.spec.max_wall_time_seconds,
            "failed_calls": self.spec.max_failed_calls,
        }
        value = mapping[unit]
        if value is None:
            return None
        return Decimal(str(value))

    def _check(self, unit: BudgetUnit, amount: Decimal) -> None:
        if amount < 0:
            raise InvariantError(f"negative budget amount for {unit}")
        limit = self._limit(unit)
        if limit is None:
            return
        if self._used[unit] + self._reserved[unit] + amount > limit:
            raise BudgetExceededError(
                f"budget exceeded: {unit} limit {limit} reached",
                technical_context=f"used={self._used[unit]} reserved={self._reserved[unit]} requested={amount}",
            )

    def reserve(self, unit: BudgetUnit, amount: Decimal | int | float) -> None:
        value = Decimal(str(amount))
        self._check(unit, value)
        self._reserved[unit] += value

    def reconcile(
        self, unit: BudgetUnit, reserved: Decimal | int | float, actual: Decimal | int | float
    ) -> None:
        reserved_dec = Decimal(str(reserved))
        actual_dec = Decimal(str(actual))
        if reserved_dec < 0 or actual_dec < 0:
            raise InvariantError("reconciliation values must be non-negative")
        if self._reserved[unit] < reserved_dec:
            raise InvariantError(f"cannot reconcile {unit}: reservation underflow")
        self._reserved[unit] -= reserved_dec
        self._used[unit] += actual_dec

    def release(self, unit: BudgetUnit, reserved: Decimal | int | float) -> None:
        reserved_dec = Decimal(str(reserved))
        if self._reserved[unit] < reserved_dec:
            raise InvariantError(f"cannot release {unit}: reservation underflow")
        self._reserved[unit] -= reserved_dec

    def used(self, unit: BudgetUnit) -> Decimal:
        return self._used[unit]

    def remaining(self, unit: BudgetUnit) -> Decimal | None:
        limit = self._limit(unit)
        if limit is None:
            return None
        return max(limit - self._used[unit] - self._reserved[unit], Decimal(0))

    def exhausted(self, unit: BudgetUnit) -> bool:
        remaining = self.remaining(unit)
        return remaining is not None and remaining <= 0

    def elapsed_wall_seconds(self) -> float:
        return time.monotonic() - self.started_monotonic

    def wall_time_expired(self) -> bool:
        if self.spec.max_wall_time_seconds is None:
            return False
        return self.elapsed_wall_seconds() > self.spec.max_wall_time_seconds

    def record_call(self, usage: TokenUsage, cost: CostEntry | None = None) -> None:
        self.reconcile("calls", 1, 1)
        self._used["input_tokens"] += Decimal(usage.input_tokens)
        self._used["output_tokens"] += Decimal(usage.output_tokens)
        self._used["total_tokens"] += Decimal(usage.total_tokens)
        if cost is not None and cost.amount is not None:
            self._used["usd"] += cost.amount.amount

    def record_failure(self) -> None:
        self._used["failed_calls"] += Decimal(1)

    def check_limits_or_raise(self) -> None:
        for unit in (
            "calls",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "usd",
            "failed_calls",
        ):
            if self.exhausted(unit):
                raise BudgetExceededError(f"budget exhausted: {unit}")
        if self.wall_time_expired():
            raise BudgetExceededError("budget exhausted: wall_time_seconds")


def money_from_any(value: Decimal | int | float | str) -> Money:
    """Parse a decimal-ish value into USD money."""
    return Money(decimal_from_any(value), "USD")
