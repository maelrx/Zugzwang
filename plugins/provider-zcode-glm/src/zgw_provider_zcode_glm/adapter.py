"""ZCode Coding Plan adapter (Anthropic-Messages wire, GLM models).

Routes ONE canonical inference call to the same local gateway the operator's
ZCode session uses (``http://127.0.0.1:8787/anthropic`` by default), so no API
key of a different account is introduced: the credential arrives as an ``env:``
reference and is resolved by the runtime (never persisted into artifacts).

Evidence contract: the full wire request/response are returned in the
``ProviderResult``; GLM ``thinking`` blocks are preserved as reasoning
telemetry (the model emits thinking even when disabled — recorded as a
limitation, not hidden).
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast

import httpx

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import (
    ProviderConnectionError,
    ProviderResponseError,
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

_THINKING_BUDGETS: dict[str, int] = {"low": 1024, "medium": 4096, "high": 8192}
_RETRY_AFTER_CAP_S = 120.0


class ZCodeGlmBackend:
    """One inference call -> one Anthropic-Messages request on the ZCode gateway."""

    backend_id = "provider.zcode_glm"
    backend_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8787/anthropic",
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        reasoning_effort: str | None = None,
        default_max_output_tokens: int = 8192,
        single_flight_lock: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._reasoning_effort = reasoning_effort
        self._default_max_output_tokens = default_max_output_tokens
        self._single_flight_lock = single_flight_lock
        self._last_wire_request: dict[str, Any] | None = None
        self._last_wire_response: dict[str, Any] | None = None
        self._client = httpx.AsyncClient(
            base_url=self._base_url, transport=transport, timeout=timeout_seconds
        )

    @property
    def descriptor(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            plugin_api=self.plugin_api,
            default_capabilities=frozenset(
                {
                    Capability.TEXT_INPUT,
                    Capability.TOOL_CALLING,
                    Capability.REASONING_CONTROL,
                    Capability.USAGE_REPORTING,
                }
            ),
            known_models=(
                ModelRef(
                    backend=self.backend_id, provider="zcode-coding-plan", model="GLM-5.3-Flash"
                ),
            ),
            limitations=(
                f"ZCode Coding Plan gateway at {self._base_url}",
                "GLM-5.3-Flash emits thinking blocks even when thinking is disabled",
                "reasoning_effort maps to thinking.budget_tokens, not a native effort level",
                "json_schema output constraint degrades to an instruction (no wire schema)",
                "cost not claimed (GATE-009 pending)",
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
        self._last_wire_request = payload
        lock_ctx = (
            _single_flight(self._single_flight_lock) if self._single_flight_lock else nullcontext()
        )
        with lock_ctx:
            try:
                response = await self._client.post(
                    "/v1/messages",
                    json=payload,
                    headers=self._headers(),
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(
                    "zcode gateway call timed out", technical_context=self._base_url
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderConnectionError(
                    "zcode gateway transport failure", technical_context=str(exc)
                ) from exc

        try:
            raw_body = response.json()
            self._last_wire_response = raw_body if isinstance(raw_body, dict) else {}
        except (ValueError, json.JSONDecodeError):
            self._last_wire_response = {}

        if response.status_code == 429:
            retry_after = _retry_after_seconds(
                cast("str | None", response.headers.get("retry-after"))
            )
            throttle_context = (
                self._base_url
                if retry_after is None
                else f"{self._base_url} retry_after={retry_after}s"
            )
            raise ProviderThrottlingError(
                "zcode gateway rate limit (429)",
                technical_context=throttle_context,
            )
        if response.status_code >= 400:
            raise ProviderServerError(
                f"zcode gateway error ({response.status_code}): {response.text[:200]}",
                technical_context=self._base_url,
            )

        body: dict[str, Any] = cast(dict[str, Any], response.json())
        error_body = body.get("error")
        if isinstance(error_body, dict):
            error_data = cast(dict[str, Any], error_body)
            detail = str(error_data.get("message") or error_data.get("type") or body)
            raise ProviderResponseError(
                "zcode gateway returned an error body", technical_context=detail[:300]
            )
        normalized = self._normalize(request, body, started)
        return ProviderResult(
            response=normalized,
            wire_request=payload,
            wire_response=body,
            reasoning_telemetry=self._reasoning_telemetry(request, body),
            wire_fidelity=WireFidelity.FULL,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"anthropic-version": "2023-06-01"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def _lower_request(self, request: ModelRequest) -> dict[str, Any]:
        system_blocks: list[str] = []
        wire_messages: list[dict[str, Any]] = []
        for message in request.messages:
            blocks: list[dict[str, Any]] = []
            for part in message.parts:
                if isinstance(part, TextPart):
                    blocks.append({"type": "text", "text": part.text})
                elif isinstance(part, JsonDataPart):
                    blocks.append(
                        {
                            "type": "text",
                            "text": json.dumps(part.data, ensure_ascii=False, sort_keys=True),
                        }
                    )
                elif isinstance(part, ImagePart):
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": part.mime,
                                "data": part.data_base64,
                            },
                        }
                    )
                elif isinstance(part, ToolCallPart):
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": part.tool_call_id,
                            "name": part.tool_name,
                            "input": part.arguments,
                        }
                    )
                elif isinstance(part, ToolResultPart):
                    blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": part.tool_call_id,
                            "content": [{"type": "text", "text": part.content}],
                            "is_error": part.is_error,
                        }
                    )
                elif message.role is not MessageRole.SYSTEM:
                    # Remaining union member is StatusPart: unsupported outside system text.
                    raise ProviderResponseError(
                        f"unsupported part type {part.type!r} in zcode_glm adapter",
                        technical_context="status parts are only lowered from system text",
                    )
            if message.role is MessageRole.SYSTEM:
                system_blocks.extend(str(b["text"]) for b in blocks if b.get("type") == "text")
                continue
            if not blocks:
                raise ProviderResponseError(
                    "zcode_glm adapter produced an empty message",
                    technical_context=f"role={message.role.value}",
                )
            wire_messages.append({"role": self._role(message.role), "content": blocks})

        if not wire_messages or wire_messages[0]["role"] != "user":
            # Anthropic-Messages requires the conversation to open with a user
            # turn (and rejects assistant-first histories with code 1214);
            # navigation continuations start at the assistant tool_use.
            wire_messages.insert(
                0,
                {"role": "user", "content": [{"type": "text", "text": "Begin."}]},
            )

        max_tokens = request.inference.max_output_tokens or self._default_max_output_tokens
        payload: dict[str, Any] = {
            "model": request.model.model,
            "max_tokens": max_tokens,
            "messages": wire_messages,
        }
        if system_blocks:
            payload["system"] = "\n\n".join(system_blocks)
        if request.inference.temperature is not None:
            payload["temperature"] = request.inference.temperature
        if request.inference.stop:
            payload["stop_sequences"] = list(request.inference.stop)
        if self._reasoning_effort:
            budget = _THINKING_BUDGETS.get(self._reasoning_effort)
            if budget is not None:
                payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
                if max_tokens <= budget:
                    payload["max_tokens"] = budget + 1024
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters or {"type": "object"},
                }
                for tool in request.tools
            ]
        if request.output_constraint.format in {"json_schema", "json_object"}:
            instruction = (
                "Respond with exactly one JSON object and no other text"
                if request.output_constraint.format == "json_object"
                else "Respond with exactly one JSON object validating the given schema"
            )
            if system_blocks:
                payload["system"] = str(payload["system"]) + "\n\n" + instruction
            else:
                payload["system"] = instruction
        return payload

    def _normalize(
        self, request: ModelRequest, body: dict[str, Any], started: Any
    ) -> NormalizedResponse:
        content_parts: list[TextPart | ToolCallPart | StatusPart] = []
        for block in cast(list[dict[str, Any]], body.get("content") or []):
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if isinstance(text, str) and text:
                    content_parts.append(TextPart(text=text))
            elif block_type == "tool_use":
                content_parts.append(
                    ToolCallPart(
                        tool_call_id=str(block.get("id", "")),
                        tool_name=str(block.get("name", "")),
                        arguments=cast(dict[str, Any], block.get("input") or {}),
                    )
                )
        usage_raw = cast(dict[str, Any], body.get("usage") or {})
        usage = TokenUsage(
            input_tokens=int(usage_raw.get("input_tokens", 0) or 0),
            output_tokens=int(usage_raw.get("output_tokens", 0) or 0),
            source=UsageSource.PROVIDER if usage_raw else UsageSource.UNKNOWN,
        )
        return NormalizedResponse(
            content_parts=tuple(content_parts),
            tool_calls=tuple(p for p in content_parts if isinstance(p, ToolCallPart)),
            stop_reason=self._map_stop(body.get("stop_reason")),
            model_requested=request.model,
            model_reported=str(body.get("model") or request.model.model),
            request_id=str(body.get("id") or ""),
            usage=usage,
            started_at=started,
            finished_at=utc_now(),
            adapter_version=self.backend_version,
            wire_fidelity=WireFidelity.FULL,
            warnings=(),
        )

    def _reasoning_telemetry(
        self, request: ModelRequest, body: dict[str, Any]
    ) -> ReasoningTelemetry:
        items: list[dict[str, Any]] = []
        thinking_texts: list[str] = []
        for block in cast(list[dict[str, Any]], body.get("content") or []):
            if block.get("type") in {"thinking", "redacted_thinking"}:
                items.append(dict(block))
                text = block.get("thinking")
                if isinstance(text, str) and text:
                    thinking_texts.append(text)
        usage_raw = cast(dict[str, Any], body.get("usage") or {})
        return ReasoningTelemetry(
            provider="zcode-coding-plan",
            model=str(body.get("model") or request.model.model),
            reasoning_effort=self._reasoning_effort,
            usage=usage_raw,
            reasoning_items=tuple(items),
            reasoning_summary="\n".join(thinking_texts) if thinking_texts else None,
            availability=ReasoningAvailability(
                reasoning_tokens=False,
                reasoning_items=bool(items),
                reasoning_summary=bool(thinking_texts),
            ),
            wire_fidelity=WireFidelity.FULL,
            provider_metadata={"gateway": self._base_url},
        )

    @staticmethod
    def _map_stop(raw: Any) -> StopReason:
        mapping = {
            "end_turn": "end_turn",
            "stop_sequence": "end_turn",
            "max_tokens": "max_tokens",
            "tool_use": "tool_calls",
            "refusal": "refusal",
        }
        canonical = mapping.get(str(raw), "unknown")
        return StopReason(canonical=canonical, raw=str(raw) if raw else None)  # type: ignore[arg-type]

    @staticmethod
    def _role(role: MessageRole) -> str:
        if role is MessageRole.TOOL:
            return "user"
        return role.value


def _retry_after_seconds(header: str | None) -> float | None:
    if not header:
        return None
    try:
        return min(float(header), _RETRY_AFTER_CAP_S)
    except ValueError:
        return None


class _single_flight:
    """Cross-process gate so at most one gateway call is in flight at a time."""

    def __init__(self, lock_path: str) -> None:
        self._lock_path = lock_path
        self._fd: int | None = None

    def __enter__(self) -> None:
        path = Path(self._lock_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
