"""Money and usage accounting.

Unknown cost is never coerced to zero: the design requires ``unknown`` to
remain visibly unknown in reports and ledgers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum


class UsageSource(StrEnum):
    """Where token usage came from."""

    PROVIDER = "provider"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class CostStatus(StrEnum):
    """How a monetary cost figure was obtained."""

    PROVIDER_REPORTED = "provider_reported"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


def decimal_from_any(value: Decimal | int | float | str) -> Decimal:
    """Convert an untrusted numeric/string into a Decimal or raise ValueError."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal value {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite decimal value {value!r}")
    return result


def _to_money_decimal(value: Decimal | int | float | str) -> Decimal:
    return decimal_from_any(value)


@dataclass(frozen=True, slots=True)
class Money:
    """A fixed-point monetary amount in a given currency (USD default)."""

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _to_money_decimal(self.amount))
        if self.amount < 0:
            raise ValueError("money amount must not be negative")
        if not self.currency:
            raise ValueError("money currency must not be empty")

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError("cannot add money in different currencies")
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: object) -> Money:
        return self.__add__(other)

    def __mul__(self, factor: object) -> Money:
        if not isinstance(factor, (int, Decimal)):
            return NotImplemented
        return Money(
            (self.amount * factor).quantize(Decimal("0.000001"), ROUND_HALF_EVEN),
            self.currency,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount < other.amount

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount <= other.amount


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage with an explicit provenance source."""

    input_tokens: int = 0
    output_tokens: int = 0
    source: UsageSource = UsageSource.UNKNOWN

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts must not be negative")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: object) -> TokenUsage:
        if not isinstance(other, TokenUsage):
            return NotImplemented
        merged = UsageSource.UNKNOWN
        if self.source is other.source:
            merged = self.source
        elif UsageSource.PROVIDER in (self.source, other.source):
            merged = UsageSource.PROVIDER
        elif UsageSource.ESTIMATED in (self.source, other.source):
            merged = UsageSource.ESTIMATED
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            source=merged,
        )


@dataclass(frozen=True, slots=True)
class CostEntry:
    """A cost line with provenance. ``None`` amount means unknown."""

    amount: Money | None
    status: CostStatus
    provider: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if self.amount is None and self.status is not CostStatus.UNKNOWN:
            raise ValueError("unknown amount must carry UNKNOWN status")

    def __add__(self, other: object) -> CostEntry:
        if not isinstance(other, CostEntry):
            return NotImplemented
        if self.amount is None or other.amount is None:
            return CostEntry(None, CostStatus.UNKNOWN)
        if self.amount.currency != other.amount.currency:
            raise ValueError("cannot add costs in different currencies")
        return CostEntry(
            amount=self.amount + other.amount,
            status=(
                CostStatus.CALCULATED
                if CostStatus.PROVIDER_REPORTED not in (self.status, other.status)
                else CostStatus.PROVIDER_REPORTED
            ),
        )


ZERO_MONEY: Money = Money(Decimal("0"), "USD")


@dataclass(slots=True)
class UsageAccumulator:
    """Mutable accumulation buffer for a run/episode ledger."""

    calls: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostEntry = CostEntry(None, CostStatus.UNKNOWN)

    def record(self, usage: TokenUsage, cost: CostEntry | None = None) -> None:
        self.calls += 1
        self.usage = self.usage + usage
        if cost is not None:
            self.cost = self.cost + cost
