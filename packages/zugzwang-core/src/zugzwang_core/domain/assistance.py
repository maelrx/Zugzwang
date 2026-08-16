"""Assistance taxonomy (design §1.1, H0-H7) and knowledge axis (K).

Every tool, verifier and dataset that influences a decision declares an
assistance impact. The effective class of a run is computed from what actually
happened, not from what the manifest declared (design §1.1 rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .errors import InvariantError


class HClass(IntEnum):
    """Operational/strategic assistance class."""

    H0 = 0  # parsing/format only
    H1 = 1  # rules checking
    H2 = 2  # environment executes state and transition
    H3 = 3  # legal action set provided
    H4 = 4  # search using models only
    H5 = 5  # engine evaluates candidates
    H6 = 6  # engine generates candidates
    H7 = 7  # engine chooses the action

    def __str__(self) -> str:
        return self.name


class KClass(IntEnum):
    """Knowledge axis: external chess knowledge injected (H and K are independent)."""

    K0 = 0  # no knowledge packet
    K1 = 1  # static general knowledge
    K2 = 2  # static position-matched knowledge
    K3 = 3  # dynamic (non-engine) retrieval
    K4 = 4  # engine-derived knowledge, delivered statically

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class AssistanceImpact:
    """A single observed assistance effect with its source."""

    h: HClass
    k: KClass = KClass.K0
    source: str = "unspecified"

    @property
    def level(self) -> tuple[int, int]:
        return (int(self.h), int(self.k))


@dataclass(frozen=True, slots=True)
class AssistanceDeclared:
    """The assistance classes a protocol declares."""

    h: HClass
    k: KClass = KClass.K0


def effective_assistance(
    impacts: tuple[AssistanceImpact, ...] | list[AssistanceImpact],
) -> tuple[HClass, KClass]:
    """Effective class is the maximum of all observed impacts (design §13.7)."""
    if not impacts:
        return (HClass.H0, KClass.K0)
    max_h = max(i.h for i in impacts)
    max_k = max(i.k for i in impacts)
    return (max_h, max_k)


@dataclass(frozen=True, slots=True)
class AssistanceAudit:
    """Declared vs. effective comparison for a run or condition."""

    declared_h: HClass
    declared_k: KClass
    effective_h: HClass
    effective_k: KClass
    violations: tuple[str, ...] = ()

    @property
    def violated(self) -> bool:
        return bool(self.violations)

    @property
    def promoted_silently(self) -> bool:
        return (self.effective_h > self.declared_h) or (self.effective_k > self.declared_k)


def audit_assistance(
    declared: AssistanceDeclared,
    observed: tuple[AssistanceImpact, ...] | list[AssistanceImpact],
) -> AssistanceAudit:
    """Compare declaration against observation.

    If the experiment declared H2 and an H5 tool was used, the run is marked as
    a protocol violation — never silently promoted (design §1.1).
    """
    eff_h, eff_k = effective_assistance(observed)
    violations: list[str] = []
    if eff_h > declared.h:
        violations.append(f"effective H{eff_h.name} exceeds declared H{declared.h.name}")
    if eff_k > declared.k:
        violations.append(f"effective K{eff_k.name} exceeds declared K{declared.k.name}")
    if not observed and eff_h < declared.h:
        raise InvariantError("assistance audit received no impacts for a non-H0 declaration")
    return AssistanceAudit(
        declared_h=declared.h,
        declared_k=declared.k,
        effective_h=eff_h,
        effective_k=eff_k,
        violations=tuple(violations),
    )
