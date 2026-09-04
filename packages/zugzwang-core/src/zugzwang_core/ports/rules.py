"""Formal rules and information-exposure contracts.

The rules kernel answers questions about a state.  The legality gateway owns
the separate decision about which of those answers may cross into a model
context.  Keeping these contracts in ``zugzwang-core`` prevents a concrete
chess library or provider from becoming the scientific boundary.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from ..domain.events import JsonValue


class ParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    parsed: Any | None = None
    error: str | None = None
    notation: str = "canonical"


class LegalityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    legal: StrictBool
    action: Any | None = None
    reason: str | None = None
    state_fingerprint: str | None = None
    assistance_h: Literal["H0", "H1", "H2", "H3"] = "H1"


class ActionHandle(BaseModel):
    """Opaque index scoped to one immutable legal-action ordering."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    ordering_hash: str


class DecisionCapabilities(BaseModel):
    """Capabilities leased to one decision phase.

    A lease is data, not a convention: strategies receive this exact object
    and the gateway refuses operations that are not leased to the phase.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    validate_action: bool = False
    enumerate_actions: bool = False
    transition_sandbox: bool = False
    query_terminal: bool = False
    validation_feedback: Literal["none", "binary", "reason_category", "enumerated"] = "none"


class LegalityValidationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    feedback: Literal["none", "binary", "reason_category", "enumerated"] = "binary"


class LegalityEnumerationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False


class LegalityLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    validations: int = Field(default=64, ge=0)
    transitions: int = Field(default=64, ge=0)
    depth_plies: int = Field(default=6, ge=0)
    branch_states: int = Field(default=64, ge=0)


class LegalityGatewayConfig(BaseModel):
    """Manifest-level exposure policy for formal rules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parse_feedback: bool = True
    validation: LegalityValidationSpec = LegalityValidationSpec()
    enumerate: LegalityEnumerationSpec = LegalityEnumerationSpec()
    transition_sandbox: bool = True
    limits: LegalityLimits = LegalityLimits()

    @property
    def validation_feedback(
        self,
    ) -> Literal["none", "binary", "reason_category", "enumerated"]:
        return self.validation.feedback

    @property
    def enumerate_enabled(self) -> bool:
        return self.enumerate.enabled


@runtime_checkable
class RulesKernel(Protocol):
    """Trusted formal authority; it never decides strategic quality."""

    def parse_action(self, raw: str, notation: str = "canonical") -> ParseResult: ...

    def is_legal(self, state: Any, action: Any) -> LegalityResult: ...

    def legal_actions(self, state: Any) -> Any: ...

    def transition(self, state: Any, action: Any) -> Any: ...

    def terminal(self, state: Any) -> Any: ...


def capability_from_config(config: LegalityGatewayConfig) -> DecisionCapabilities:
    """Build the broad capability lease for a phase that is explicitly allowed."""
    return DecisionCapabilities(
        validate_action=config.validation.enabled,
        enumerate_actions=config.enumerate.enabled,
        transition_sandbox=config.transition_sandbox,
        query_terminal=config.transition_sandbox,
        validation_feedback=config.validation.feedback,
    )


def json_capabilities(capabilities: DecisionCapabilities) -> dict[str, JsonValue]:
    """Stable serialization used in observations and decision evidence."""
    return capabilities.model_dump(mode="json")
