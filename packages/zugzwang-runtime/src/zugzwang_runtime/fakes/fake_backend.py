"""DeterministicModelBackend: scripted responses for offline tests (design §24.2).

Rules match on call index or request fingerprint. Responses can be text,
structured JSON, or scripted failures (rate_limit, timeout, server_error).
Every call records a NormalizedResponse with estimated usage and full wire
fidelity — the fake is fully transparent.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import (
    ProviderServerError,
    ProviderThrottlingError,
    ProviderTimeoutError,
)
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    StopReason,
    TextPart,
    WireFidelity,
)


class FakeBackendRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    when: dict[
        Literal["call_index", "fingerprint_contains", "call_index_modulo"], int | str | list[int]
    ]
    output: str | dict[str, JsonValue] | None = None
    raise_: Literal["rate_limit", "timeout", "server_error"] | None = Field(
        default=None, alias="raise"
    )

    def matches(self, call_index: int, fingerprint: str | None) -> bool:
        results: list[bool] = []
        if "call_index" in self.when:
            results.append(self.when["call_index"] == call_index)
        if "call_index_modulo" in self.when:
            parts = self.when["call_index_modulo"]
            if isinstance(parts, list) and len(parts) == 2:
                results.append(call_index % int(parts[0]) == int(parts[1]))
        if "fingerprint_contains" in self.when:
            needle = str(self.when["fingerprint_contains"])
            results.append(fingerprint is not None and needle in fingerprint)
        return bool(results) and all(results)


class DeterministicModelBackend:
    """Scripted backend implementing the canonical ModelBackend port."""

    backend_id = "fake.backend"
    backend_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self, rules: tuple[FakeBackendRule, ...] = (), *, latency_seconds: float = 0.0
    ) -> None:
        self._rules = rules
        self._call_count = 0
        self._latency_seconds = latency_seconds

    @property
    def descriptor(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            plugin_api=self.plugin_api,
            default_capabilities=frozenset(
                {
                    Capability.TEXT_INPUT,
                    Capability.JSON_SCHEMA_OUTPUT,
                    Capability.USAGE_REPORTING,
                    Capability.SEED,
                }
            ),
            known_models=(ModelRef(backend=self.backend_id, provider="fake", model="scripted"),),
            limitations=("scripted responses; no network",),
        )

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport:
        supported = self.descriptor.default_capabilities
        missing_required = frozenset(c for c in required if c not in supported)
        missing_preferred = frozenset(c for c in preferred if c not in supported)
        return CapabilityReport(
            model=model,
            supported=supported,
            missing_required=missing_required,
            missing_preferred=missing_preferred,
            on_unsupported=on_unsupported,
        )

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        if self._latency_seconds > 0:
            await asyncio.sleep(self._latency_seconds)
        index = self._call_count
        self._call_count += 1
        started = utc_now()
        for rule in self._rules:
            if rule.matches(index, context.fingerprint):
                if rule.raise_ == "rate_limit":
                    raise ProviderThrottlingError(
                        "fake rate limit", technical_context=f"call_index={index}"
                    )
                if rule.raise_ == "timeout":
                    raise ProviderTimeoutError(
                        "fake timeout", technical_context=f"call_index={index}"
                    )
                if rule.raise_ == "server_error":
                    raise ProviderServerError(
                        "fake server error", technical_context=f"call_index={index}"
                    )
                if isinstance(rule.output, str):
                    content: tuple[TextPart, ...] = (TextPart(text=rule.output),)
                else:
                    from zugzwang_core.domain.canonical import canonical_json_string

                    content = (TextPart(text=canonical_json_string(rule.output)),)
                response = self._response(request, context, content, started)
                return ProviderResult(response=response)
        raise ProviderServerError(
            "no fake rule matched",
            technical_context=f"call_index={index} rules={len(self._rules)}",
        )

    def _response(
        self,
        request: ModelRequest,
        context: CallContext,
        content: tuple[TextPart, ...],
        started: datetime,
    ) -> NormalizedResponse:
        text = "".join(part.text for part in content)
        usage = TokenUsage(
            input_tokens=max(len(str(request.model_dump(mode="json"))) // 4, 1),
            output_tokens=max(len(text) // 4, 1),
            source=UsageSource.ESTIMATED,
        )
        return NormalizedResponse(
            content_parts=content,
            stop_reason=StopReason(canonical="end_turn"),
            model_requested=request.model,
            model_reported=f"{request.model.provider}:{request.model.model}",
            request_id=f"fake-req-{context.attempt_id or 'n/a'}",
            usage=usage,
            started_at=started,
            finished_at=utc_now(),
            adapter_version=self.backend_version,
            wire_fidelity=WireFidelity.FULL,
        )


class FakeBackendDefinition:
    """Entry-point shaped wrapper so the registry treats the fake uniformly."""

    def __init__(self) -> None:
        self._descriptor = None

    @property
    def descriptor(self):
        from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

        if self._descriptor is None:
            self._descriptor = PluginDescriptor(
                plugin_id="fake.backend",
                plugin_version="0.1.0",
                kind=PluginKind.PROVIDER,
                capabilities=("text_input", "json_schema_output", "seed"),
                license="GPL-3.0-or-later",
                trust=TrustLevel.FIRST_PARTY,
            )
        return self._descriptor
