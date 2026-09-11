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
    CapabilityMissingError,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderServerError,
    ProviderThrottlingError,
    ProviderTimeoutError,
)
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.domain.provider_isolation import reject_native_execution
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    ImagePart,
    JsonDataPart,
    MessageRole,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    ReasoningAvailability,
    ReasoningTelemetry,
    StatusPart,
    StopReason,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    WireFidelity,
)

_RESPONSES_PROFILE = "openai-responses"


def _single_flight_lock():
    """Cross-process single-flight gate for ONE shared provider quota.

    ZGX campaign contract (plano 28 §3.1): one Muse inference in flight per
    shared quota domain, not one per workspace. When ZGZ_MUSE_SINGLE_FLIGHT_LOCK
    names a lock file, every wire call holds an exclusive flock for its
    duration; concurrent run processes serialize at the HTTP boundary (their
    non-provider work — engine moves, persistence — stays parallel).
    """
    import contextlib
    import fcntl
    import os

    lock_path = os.environ.get("ZGZ_MUSE_SINGLE_FLIGHT_LOCK", "")
    if not lock_path:

        @contextlib.contextmanager
        def _noop():
            yield

        return _noop()

    @contextlib.contextmanager
    def _gate():
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    return _gate()


def _retry_after_seconds(headers: Any) -> float | None:
    """Provider's Retry-After hint in seconds; None when absent or non-numeric
    (HTTP-date form is deliberately unsupported — no clock guessing)."""
    raw: Any = headers.get("retry-after") if headers is not None else None
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


class OpenAiCompatibleBackend:
    """One-inference backend over an explicit OpenAI-compatible wire profile."""

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
        reasoning_effort: str | None = None,
        default_max_output_tokens: int | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._profile = profile
        self._allow_private_network = allow_private_network
        self._image_input = image_input
        self._reasoning_effort = reasoning_effort
        self._default_max_output_tokens = default_max_output_tokens
        self._last_wire_request: dict[str, Any] | None = None
        self._last_wire_response: dict[str, Any] | None = None
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
                f"reasoning effort configured by operator: {self._reasoning_effort or 'provider-default'}",
            ),
        )

    def _require_supported_parts(self, request: ModelRequest) -> None:
        """Refuse image parts before any wire call when image input is off.

        TEST-065: no silent image-to-text fallback — the refusal happens in
        the adapter itself, before persistence or transport, mirroring the
        RecordingBackend required-capabilities enforcement.
        """
        needs_image = any(
            isinstance(part, ImagePart) for message in request.messages for part in message.parts
        )
        if needs_image and Capability.MULTIMODAL_IMAGE not in self.descriptor.default_capabilities:
            raise CapabilityMissingError(
                f"backend {self.backend_id} lacks required capabilities: multimodal_image"
            )
        if request.required_capabilities:
            missing = [
                str(capability)
                for capability in request.required_capabilities
                if capability not in self.descriptor.default_capabilities
            ]
            if missing:
                raise CapabilityMissingError(
                    f"backend {self.backend_id} lacks required capabilities: "
                    + ", ".join(sorted(missing))
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
        self._require_supported_parts(request)
        is_responses = self._profile == _RESPONSES_PROFILE
        payload = (
            self._lower_responses_request(request) if is_responses else self._lower_request(request)
        )
        self._last_wire_request = payload
        endpoint = "/responses" if is_responses else "/chat/completions"
        try:
            with _single_flight_lock():
                response = await self._client.post(endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "provider call timed out", technical_context=self._base_url
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(
                "provider transport failure", technical_context=str(exc)
            ) from exc

        try:
            raw_body = response.json()
            self._last_wire_response = raw_body if isinstance(raw_body, dict) else {}
        except (ValueError, json.JSONDecodeError):
            self._last_wire_response = {}

        if response.status_code == 429:
            raise ProviderThrottlingError(
                "provider rate limit (429)",
                technical_context=self._base_url,
                retry_after=_retry_after_seconds(response.headers),
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
        reject_native_execution(body)
        normalized = (
            self._raise_responses_response(request, body, started, context)
            if is_responses
            else self._raise_response(request, body, started, context)
        )
        return ProviderResult(
            response=normalized,
            wire_request=payload,
            wire_response=body,
            reasoning_telemetry=self._reasoning_telemetry(request, body),
            wire_fidelity=WireFidelity.FULL,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _lower_request(self, request: ModelRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            role = self._role(message.role)
            text_parts = [p.text for p in message.parts if isinstance(p, TextPart)]
            json_parts = [
                json.dumps(p.data, ensure_ascii=False, sort_keys=True)
                for p in message.parts
                if isinstance(p, JsonDataPart)
            ]
            image_parts = [p for p in message.parts if isinstance(p, ImagePart)]
            call_parts = [p for p in message.parts if isinstance(p, ToolCallPart)]
            result_parts = [p for p in message.parts if isinstance(p, ToolResultPart)]
            if call_parts or result_parts:
                if message.role is MessageRole.TOOL:
                    if call_parts or text_parts or image_parts or json_parts:
                        raise ProviderResponseError(
                            "tool messages must use ToolResultPart in chat lowering",
                            technical_context="TOOL messages carry tool results only",
                        )
                    for part in result_parts:
                        messages.append(
                            {
                                "role": role,
                                "tool_call_id": part.tool_call_id,
                                "content": part.content,
                            }
                        )
                    continue
                if result_parts:
                    raise ProviderResponseError(
                        "tool results require the TOOL role in chat lowering",
                        technical_context="ToolResultPart must ride a TOOL message",
                    )
                entry: dict[str, Any] = {
                    "role": role,
                    # JSON command envelopes ride the text channel; images never
                    # mix with tool calls (image shapes are refused in
                    # _require_supported_parts when unsupported).
                    "content": "\n".join(text_parts + json_parts) or None,
                }
                if call_parts:
                    entry["tool_calls"] = [
                        {
                            "id": part.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": part.tool_name,
                                "arguments": json.dumps(
                                    part.arguments, ensure_ascii=False, sort_keys=True
                                ),
                            },
                        }
                        for part in call_parts
                    ]
                messages.append(entry)
                continue
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
                content = "\n".join(text_parts + json_parts)
            entry = {"role": role, "content": content}
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
        payload.update(self._wire_extensions(request))
        return payload

    def _reasoning_telemetry(
        self, request: ModelRequest, body: dict[str, Any]
    ) -> ReasoningTelemetry:
        """Preserve provider-exposed reasoning fields without calling them CoT."""
        items: list[dict[str, Any]] = []
        summaries: list[str] = []
        output_raw = body.get("output")
        output_items: list[dict[str, Any]] = (
            cast(list[dict[str, Any]], output_raw) if isinstance(output_raw, list) else []
        )
        for item in output_items:
            if item.get("type") != "reasoning":
                continue
            items.append(dict(item))
            raw_summary = item.get("summary")
            if isinstance(raw_summary, list):
                summary_items = cast(list[Any], raw_summary)
                for entry in summary_items:
                    entry_data = cast(dict[str, Any], entry) if isinstance(entry, dict) else {}
                    if isinstance(entry_data.get("text"), str):
                        summaries.append(str(entry_data["text"]))
                    elif isinstance(entry, str):
                        summaries.append(entry)
            elif isinstance(raw_summary, str):
                summaries.append(raw_summary)
        choices_raw = body.get("choices")
        choices: list[dict[str, Any]] = (
            cast(list[dict[str, Any]], choices_raw) if isinstance(choices_raw, list) else []
        )
        if choices:
            message_raw = choices[0].get("message")
            message = cast(dict[str, Any], message_raw) if isinstance(message_raw, dict) else {}
            exposed = message.get("reasoning_content") or message.get("reasoning")
            if isinstance(exposed, str) and exposed:
                summaries.append(exposed)
        usage_raw = body.get("usage")
        usage_data: dict[str, Any] = (
            cast(dict[str, Any], usage_raw) if isinstance(usage_raw, dict) else {}
        )
        details_raw = usage_data.get("output_tokens_details")
        details: dict[str, Any] = (
            cast(dict[str, Any], details_raw) if isinstance(details_raw, dict) else {}
        )
        reasoning_raw = details.get("reasoning_tokens")
        reasoning_tokens = int(reasoning_raw) if reasoning_raw is not None else None
        return ReasoningTelemetry(
            provider=request.model.provider,
            model=str(body.get("model") or request.model.model),
            reasoning_effort=self._reasoning_effort,
            reasoning_tokens=reasoning_tokens,
            usage=usage_data,
            reasoning_items=tuple(items),
            reasoning_summary="\n".join(summaries) if summaries else None,
            availability=ReasoningAvailability(
                reasoning_tokens=reasoning_tokens is not None,
                reasoning_items=bool(items),
                reasoning_summary=bool(summaries),
            ),
            wire_fidelity=WireFidelity.FULL,
        )

    @staticmethod
    def _wire_extensions(request: ModelRequest) -> dict[str, Any]:
        """Forward only extensions explicitly intended for this wire adapter."""
        prefix = "provider.openai_compatible."
        return {
            key.removeprefix(prefix): value
            for key, value in request.extensions.items()
            if key.startswith(prefix) and key.removeprefix(prefix)
        }

    def _lower_responses_request(self, request: ModelRequest) -> dict[str, Any]:
        """Lower the canonical request to the OpenAI Responses API shape."""
        input_items: list[dict[str, Any]] = []
        for message in request.messages:
            pending_content: list[dict[str, Any]] = []
            text_type = "output_text" if message.role is MessageRole.ASSISTANT else "input_text"
            for part in message.parts:
                if isinstance(part, TextPart):
                    pending_content.append({"type": text_type, "text": part.text})
                elif isinstance(part, ImagePart):
                    pending_content.append({"type": "input_image", "image_url": part.data_url()})
                elif isinstance(part, JsonDataPart):
                    pending_content.append(
                        {
                            "type": text_type,
                            "text": json.dumps(part.data, ensure_ascii=False, sort_keys=True),
                        }
                    )
                elif isinstance(part, ToolCallPart):
                    if part.tool_call_id.startswith("harness:"):
                        # Synthetic harness calls carry no provider-issued
                        # reasoning; DeepSeek thinking upstreams (Console Go)
                        # reject them as function_call items that lack the
                        # originating reasoning_text. Lower them to plain text.
                        pending_content.append(
                            {
                                "type": text_type,
                                "text": (
                                    f"[harness tool call] {part.tool_name}"
                                    f"({json.dumps(part.arguments, ensure_ascii=False, sort_keys=True)})"
                                ),
                            }
                        )
                        continue
                    if pending_content:
                        input_items.append({"role": message.role.value, "content": pending_content})
                        pending_content = []
                    input_items.append(
                        {
                            "type": "function_call",
                            "call_id": part.tool_call_id,
                            "name": part.tool_name,
                            "arguments": json.dumps(
                                part.arguments, ensure_ascii=False, sort_keys=True
                            ),
                        }
                    )
                elif isinstance(part, ToolResultPart):
                    if part.tool_call_id.startswith("harness:"):
                        if pending_content:
                            input_items.append(
                                {"role": message.role.value, "content": pending_content}
                            )
                            pending_content = []
                        input_items.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": f"[harness tool result] {part.content}",
                                    }
                                ],
                            }
                        )
                        continue
                    if pending_content:
                        input_items.append({"role": message.role.value, "content": pending_content})
                        pending_content = []
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": part.tool_call_id,
                            "output": part.content,
                        }
                    )
                else:
                    raise ProviderResponseError(
                        f"unsupported part type {part.type!r} in Responses adapter",
                        technical_context="responses lowering supports text, image, JSON and function call parts",
                    )
            if pending_content:
                if message.role is MessageRole.TOOL:
                    raise ProviderResponseError(
                        "tool messages must use ToolResultPart in Responses adapter"
                    )
                input_items.append({"role": message.role.value, "content": pending_content})

        payload: dict[str, Any] = {
            "model": request.model.model,
            "input": input_items,
        }
        max_output_tokens = request.inference.max_output_tokens or self._default_max_output_tokens
        if max_output_tokens:
            payload["max_output_tokens"] = max_output_tokens
        if request.inference.temperature is not None:
            payload["temperature"] = request.inference.temperature
        if request.inference.seed is not None:
            payload["seed"] = request.inference.seed
        if request.inference.stop:
            payload["stop"] = list(request.inference.stop)
        if self._reasoning_effort:
            # Operator directive 2026-09-08: request readable reasoning
            # summaries — the telemetry contract already carries
            # reasoning_summary; the encrypted items stay as raw evidence.
            payload["reasoning"] = {"effort": self._reasoning_effort, "summary": "auto"}
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
                for tool in request.tools
            ]
        if request.output_constraint.format == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        elif request.output_constraint.format == "json_schema":
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "response",
                    "schema": request.output_constraint.schema_ or {},
                    "strict": True,
                }
            }
        payload.update(self._wire_extensions(request))
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

    def _raise_responses_response(
        self, request: ModelRequest, body: dict[str, Any], started: Any, context: CallContext
    ) -> NormalizedResponse:
        """Normalize a non-streaming OpenAI Responses API response."""
        status = body.get("status")
        if status == "failed":
            error = body.get("error")
            error_data = cast(dict[str, Any], error) if isinstance(error, dict) else {}
            detail_value = error_data.get("message") if error_data else None
            detail = str(detail_value) if detail_value else "provider returned an error"
            raise ProviderServerError(
                "provider returned a failed Responses result",
                technical_context=str(detail or body)[:300],
            )

        content_parts: list[TextPart | StatusPart | ToolCallPart] = []
        output_raw = body.get("output")
        output_items: list[dict[str, Any]] = (
            cast(list[dict[str, Any]], output_raw) if isinstance(output_raw, list) else []
        )
        for item_raw in output_items:
            item_type = item_raw.get("type")
            if item_type == "message":
                content = item_raw.get("content")
                if not isinstance(content, list):
                    continue
                content_items = cast(list[dict[str, Any]], content)
                for part_raw in content_items:
                    part_type = part_raw.get("type")
                    text = part_raw.get("text")
                    if part_type in {"output_text", "text"} and isinstance(text, str):
                        content_parts.append(TextPart(text=text))
                    elif part_type == "refusal":
                        content_parts.append(
                            StatusPart(
                                kind="refusal",
                                message=str(part_raw.get("refusal") or text or ""),
                            )
                        )
            elif item_type == "function_call":
                raw_arguments = item_raw.get("arguments") or "{}"
                try:
                    arguments: dict[str, Any] = json.loads(str(raw_arguments))
                except json.JSONDecodeError:
                    arguments = {"raw": str(raw_arguments)}
                content_parts.append(
                    ToolCallPart(
                        tool_call_id=str(item_raw.get("call_id") or item_raw.get("id") or ""),
                        tool_name=str(item_raw.get("name") or ""),
                        arguments=arguments,
                    )
                )

        if not any(isinstance(part, TextPart) for part in content_parts):
            output_text = body.get("output_text")
            if isinstance(output_text, str) and output_text:
                content_parts.append(TextPart(text=output_text))

        incomplete_details_raw = body.get("incomplete_details")
        incomplete_details = (
            cast(dict[str, Any], incomplete_details_raw)
            if isinstance(incomplete_details_raw, dict)
            else {}
        )
        incomplete_reason = incomplete_details.get("reason")
        if status == "completed":
            stop_reason = StopReason(canonical="end_turn", raw=str(status))
        elif status == "incomplete" and incomplete_reason == "max_output_tokens":
            stop_reason = StopReason(canonical="max_tokens", raw=str(incomplete_reason))
        elif status == "failed":
            stop_reason = StopReason(canonical="error", raw=str(status))
        else:
            stop_reason = StopReason(canonical="unknown", raw=str(status) if status else None)

        usage_raw = body.get("usage")
        usage: dict[str, Any] = (
            cast(dict[str, Any], usage_raw) if isinstance(usage_raw, dict) else {}
        )
        token_usage = TokenUsage(
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            source=UsageSource.PROVIDER if usage else UsageSource.UNKNOWN,
        )
        return NormalizedResponse(
            content_parts=tuple(content_parts),
            tool_calls=tuple(part for part in content_parts if isinstance(part, ToolCallPart)),
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
