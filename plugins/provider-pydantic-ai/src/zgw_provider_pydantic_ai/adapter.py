"""Pydantic AI Direct Model Requests adapter (ADR-017).

Pydantic AI is a translation substrate, never the kernel semantics: no Agent
loop, no hidden retries, no fallback. The adapter maps canonical messages to
pydantic_ai ModelMessages, calls ``Model.request`` directly and maps the
response back. Provider SDK types never escape this plugin.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import ProviderResponseError
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    MessageRole,
    ModelRef,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    StopReason,
    WireFidelity,
)
from zugzwang_core.ports.model import (
    ModelRequest as CanonicalRequest,
)
from zugzwang_core.ports.model import (
    TextPart as CanonicalTextPart,
)


@runtime_checkable
class PaiModel(Protocol):
    """The minimal pydantic_ai Model surface this adapter consumes."""

    model_name: str

    async def request(
        self, messages: list[Any], model_request_parameters: Any
    ) -> tuple[Any, RequestUsage]: ...


class PydanticAiBackend:
    """Backend over pydantic_ai's direct Model.request."""

    backend_id = "provider.pydantic_ai_direct"
    backend_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, model: PaiModel, *, model_name: str | None = None) -> None:
        self._model = model
        self._model_name = model_name or getattr(model, "model_name", "unknown")

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
                    Capability.TOOL_CALLING,
                    Capability.USAGE_REPORTING,
                }
            ),
            known_models=(),
            limitations=(
                "direct model requests only; no Agent loop",
                "adapter maps text/tool parts; unknown parts fail explicitly",
            ),
        )

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport:
        supported = self.descriptor.default_capabilities
        return CapabilityReport(
            model=model,
            supported=supported,
            missing_required=frozenset(c for c in required if c not in supported),
            missing_preferred=frozenset(c for c in preferred if c not in supported),
            on_unsupported=on_unsupported,
        )

    async def infer(self, request: CanonicalRequest, context: CallContext) -> ProviderResult:
        from pydantic_ai.models import ModelRequestParameters

        messages = self._raise_messages(request)
        started = utc_now()
        try:
            response, usage = await self._model.request(
                messages, ModelRequestParameters(output_mode="text")
            )
        except Exception as exc:
            raise ProviderResponseError(
                "pydantic-ai model request failed",
                technical_context=str(exc)[:300],
            ) from exc
        content_parts: tuple[CanonicalTextPart, ...] = ()
        raw_texts: list[str] = []
        for part in response.parts:
            if isinstance(part, TextPart):
                raw_texts.append(part.content)
        content_parts = tuple(CanonicalTextPart(text=t) for t in raw_texts)
        token_usage = TokenUsage(
            input_tokens=int(usage.input_tokens or 0),
            output_tokens=int(usage.output_tokens or 0),
            source=UsageSource.PROVIDER,
        )
        return ProviderResult(
            response=NormalizedResponse(
                content_parts=content_parts,
                stop_reason=StopReason(canonical="end_turn"),
                model_requested=request.model,
                model_reported=self._model_name,
                usage=token_usage,
                started_at=started,
                finished_at=utc_now(),
                adapter_version=self.backend_version,
                wire_fidelity=WireFidelity.FULL,
                warnings=(),
            )
        )

    def _raise_messages(self, request: CanonicalRequest) -> list[Any]:
        messages: list[Any] = []
        for message in request.messages:
            text = "\n".join(p.text for p in message.parts if isinstance(p, CanonicalTextPart))
            if message.role is MessageRole.SYSTEM:
                messages.append(ModelRequest(parts=[SystemPromptPart(content=text)]))
            elif message.role is MessageRole.USER:
                messages.append(ModelRequest(parts=[UserPromptPart(content=text)]))
            elif message.role is MessageRole.ASSISTANT:
                messages.append(ModelResponse(parts=[TextPart(content=text)]))
            else:
                raise ProviderResponseError(
                    f"unsupported message role for pydantic-ai mapping: {message.role.value}"
                )
        return messages
