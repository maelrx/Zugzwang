"""OpenAI-compatible adapter: direct httpx client behind the canonical contract.

First-party because OpenAI-compatible endpoints are common (vLLM, SGLang,
Ollama, gateways). "Compatible" never means semantically identical: the
adapter records its profile and probes capabilities honestly (ADR-018).
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import (
    ProviderConnectionError,
    ProviderServerError,
    ProviderThrottlingError,
    ProviderTimeoutError,
)
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    ImagePart,
    MessageRole,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    StatusPart,
    StopReason,
    TextPart,
    ToolCallPart,
    WireFidelity,
)


class OpenAiCompatibleBackend:
    """One-inference backend over an OpenAI-compatible chat/completions endpoint."""

    backend_id = "provider.openai_compatible"
    backend_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 60.0,
        profile: str = "openai-chat-completions",
        allow_private_network: bool = False,
        image_input: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._profile = profile
        self._allow_private_network = allow_private_network
        self._image_input = image_input
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            transport=transport,
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                "Content-Type": "application/json",
            },
        )

    @property
    def descriptor(self) -> BackendDescriptor:
        capabilities = {
            Capability.TEXT_INPUT,
            Capability.JSON_SCHEMA_OUTPUT,
            Capability.TOOL_CALLING,
            Capability.USAGE_REPORTING,
            Capability.SEED,
        }
        if self._image_input:
            capabilities.add(Capability.MULTIMODAL_IMAGE)
        return BackendDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            plugin_api=self.plugin_api,
            default_capabilities=frozenset(capabilities),
            known_models=(),
            limitations=(
                f"profile={self._profile}",
                "capabilities are profile defaults; probe before relying on them",
                f"image input declared by operator: {self._image_input}",
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

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        started = utc_now()
        payload = self._lower_request(request)
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "provider call timed out", technical_context=self._base_url
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(
                "provider transport failure", technical_context=str(exc)
            ) from exc

        if response.status_code == 429:
            raise ProviderThrottlingError(
                "provider rate limit (429)", technical_context=self._base_url
            )
        if response.status_code >= 500:
            raise ProviderServerError(
                f"provider server error ({response.status_code})",
                technical_context=self._base_url,
            )
        if response.status_code >= 400:
            raise ProviderServerError(
                f"provider error ({response.status_code}): {response.text[:200]}",
                technical_context=self._base_url,
            )

        body: dict[str, Any] = response.json()
        normalized = self._raise_response(request, body, started, context)
        return ProviderResult(response=normalized)

    async def close(self) -> None:
        await self._client.aclose()

    def _lower_request(self, request: ModelRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            role = self._role(message.role)
            text_parts = [p.text for p in message.parts if isinstance(p, TextPart)]
            image_parts = [p for p in message.parts if isinstance(p, ImagePart)]
            if image_parts and not text_parts:
                content: Any = [
                    {
                        "type": "image_url",
                        "image_url": {"url": part.data_url()},
                    }
                    for part in image_parts
                ]
            elif image_parts:
                content = [{"type": "text", "text": "\n".join(text_parts)}] + [
                    {"type": "image_url", "image_url": {"url": part.data_url()}}
                    for part in image_parts
                ]
            else:
                content = "\n".join(text_parts)
            entry: dict[str, Any] = {"role": role, "content": content}
            messages.append(entry)
        payload: dict[str, Any] = {
            "model": request.model.model,
            "messages": messages,
        }
        if request.inference.max_output_tokens:
            payload["max_tokens"] = request.inference.max_output_tokens
        if request.inference.temperature is not None:
            payload["temperature"] = request.inference.temperature
        if request.inference.seed is not None:
            payload["seed"] = request.inference.seed
        if request.output_constraint.format in {"json_schema", "json_object"}:
            payload["response_format"] = {"type": "json_object"}
            if request.output_constraint.schema_ is not None:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": request.output_constraint.schema_,
                    },
                }
        payload.update(request.extensions)
        return payload

    def _raise_response(
        self, request: ModelRequest, body: dict[str, Any], started: Any, context: CallContext
    ) -> NormalizedResponse:
        choices: list[dict[str, Any]] = list(cast(list[dict[str, Any]], body.get("choices") or []))
        content_parts: list[TextPart | StatusPart | ToolCallPart] = []
        stop_reason = StopReason(canonical="unknown")
        if choices:
            choice: dict[str, Any] = dict(choices[0])
            message: dict[str, Any] = dict(choice.get("message") or {})
            text = message.get("content")
            if isinstance(text, str) and text:
                content_parts.append(TextPart(text=text))
            for tool_call_raw in cast(list[dict[str, Any]], message.get("tool_calls") or []):
                tool_call: dict[str, Any] = dict(tool_call_raw)
                function: dict[str, Any] = dict(tool_call.get("function") or {})
                raw_arguments = function.get("arguments") or "{}"
                try:
                    arguments: dict[str, Any] = json.loads(str(raw_arguments))
                except json.JSONDecodeError:
                    arguments = {"raw": str(raw_arguments)}
                content_parts.append(
                    ToolCallPart(
                        tool_call_id=str(tool_call.get("id", "")),
                        tool_name=str(function.get("name", "")),
                        arguments=arguments,
                    )
                )
            finish = choice.get("finish_reason")
            stop_reason = self._map_stop(finish)
        usage: dict[str, Any] = dict(cast(dict[str, Any], body.get("usage") or {}))
        token_usage = TokenUsage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            source=UsageSource.PROVIDER if usage else UsageSource.UNKNOWN,
        )
        return NormalizedResponse(
            content_parts=tuple(content_parts),
            tool_calls=tuple(p for p in content_parts if isinstance(p, ToolCallPart)),
            stop_reason=stop_reason,
            model_requested=request.model,
            model_reported=str(body.get("model") or request.model.model),
            request_id=str(body.get("id") or ""),
            usage=token_usage,
            started_at=started,
            finished_at=utc_now(),
            adapter_version=self.backend_version,
            wire_fidelity=WireFidelity.FULL,
            warnings=(),
        )

    @staticmethod
    def _map_stop(finish: Any) -> StopReason:
        if finish == "stop":
            return StopReason(canonical="end_turn", raw=str(finish))
        if finish == "length":
            return StopReason(canonical="max_tokens", raw=str(finish))
        if finish == "tool_calls":
            return StopReason(canonical="tool_calls", raw=str(finish))
        if finish == "content_filter":
            return StopReason(canonical="content_filter", raw=str(finish))
        return StopReason(canonical="unknown", raw=str(finish) if finish else None)

    @staticmethod
    def _role(role: MessageRole) -> str:
        return role.value if role is not MessageRole.TOOL else "tool"
