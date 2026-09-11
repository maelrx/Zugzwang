"""opencode headless-server adapter.

The opencode server (``opencode serve``) exposes a session/message HTTP API.
This adapter maps ONE canonical ModelRequest to ONE opencode session+message,
so calls stay isolated: no hidden cross-call context, no agent loop, no
fallback. Usage reported by opencode is recorded with ``source=provider``;
cost stays ``unknown`` (GATE-009). Errors map to the typed provider taxonomy.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from zugzwang_core.domain.clocks import utc_now
from zugzwang_core.domain.errors import (
    ProviderConnectionError,
    ProviderResponseError,
    ProviderServerError,
    ProviderThrottlingError,
)
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.domain.provider_isolation import ProviderIsolationError, reject_native_execution
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    ImagePart,
    ModelRef,
    ModelRequest,
    NormalizedResponse,
    OnUnsupported,
    ProviderResult,
    ReasoningAvailability,
    ReasoningTelemetry,
    StopReason,
    TextPart,
    WireFidelity,
)


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


class OpenCodeBackend:
    """One inference call -> one opencode session message."""

    backend_id = "provider.opencode"
    backend_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:4100",
        provider_id: str = "opencode",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 300.0,
        image_input: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._provider_id = provider_id
        self._image_input = image_input
        self._last_wire_request: dict[str, Any] | None = None
        self._last_wire_response: dict[str, Any] | None = None
        self._client = httpx.AsyncClient(
            base_url=self._base_url, transport=transport, timeout=timeout_seconds
        )

    @property
    def descriptor(self) -> BackendDescriptor:
        capabilities = {
            Capability.TEXT_INPUT,
            Capability.USAGE_REPORTING,
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
                f"opencode server at {self._base_url}",
                "one session per call (context isolation)",
                "no tool_calling via this adapter in v0.1",
                "cost not claimed (GATE-009 pending)",
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
        session_id = await self._create_session(request.model)
        try:
            return await self._prompt(session_id, request, context, started)
        finally:
            await self._dispose_session(session_id)

    async def _create_session(self, model: ModelRef) -> str:
        try:
            response = await self._client.post(
                "/session",
                json={
                    "title": "zugzwang-call",
                    "permission": [{"permission": "*", "pattern": "*", "action": "deny"}],
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(
                "opencode server unreachable",
                technical_context=f"{self._base_url}: {exc}",
            ) from exc
        if response.status_code >= 400:
            raise ProviderServerError(
                f"opencode session creation failed ({response.status_code})",
                technical_context=response.text[:200],
            )
        data: dict[str, Any] = cast(dict[str, Any], response.json())
        session_id = data.get("id")
        if not isinstance(session_id, str):
            raise ProviderResponseError(
                "opencode session response has no id",
                technical_context=str(data)[:200],
            )
        expected = [{"permission": "*", "pattern": "*", "action": "deny"}]
        if data.get("permission") != expected:
            await self._dispose_session(session_id)
            raise ProviderIsolationError(
                "OpenCode refused or omitted the deny-all session policy; inference blocked.",
                wire_response=data,
            )
        return session_id

    async def _prompt(
        self,
        session_id: str,
        request: ModelRequest,
        context: CallContext,
        started: Any,
    ) -> ProviderResult:
        parts: list[dict[str, Any]] = []
        for message in request.messages:
            for part in message.parts:
                if isinstance(part, TextPart):
                    parts.append({"type": "text", "text": part.text})
                elif isinstance(part, ImagePart):
                    parts.append(
                        {
                            "type": "file",
                            "mime": part.mime,
                            "filename": f"observation.{part.mime.split('/')[-1]}",
                            "url": part.data_url(),
                        }
                    )
                else:
                    raise ProviderResponseError(
                        f"unsupported part type {part.type!r} in opencode adapter",
                        technical_context="parts are text or image only in v0.1",
                    )
        try:
            self._last_wire_request = {
                "model": {
                    "providerID": self._provider_id,
                    "modelID": request.model.model,
                },
                "parts": parts,
            }
            response = await self._client.post(
                f"/session/{session_id}/message",
                json={
                    "model": {
                        "providerID": self._provider_id,
                        "modelID": request.model.model,
                    },
                    "parts": parts,
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(
                "opencode message call failed", technical_context=str(exc)
            ) from exc
        try:
            raw_data = response.json()
            self._last_wire_response = raw_data if isinstance(raw_data, dict) else {}
        except (ValueError, json.JSONDecodeError):
            self._last_wire_response = {}
        if response.status_code == 429:
            raise ProviderThrottlingError(
                "opencode rate limited (429)",
                technical_context=self._base_url,
                retry_after=_retry_after_seconds(response.headers),
            )
        if response.status_code >= 400:
            raise ProviderServerError(
                f"opencode message call failed ({response.status_code})",
                technical_context=response.text[:200],
            )
        data: dict[str, Any] = cast(dict[str, Any], response.json())
        reject_native_execution(data)
        info: dict[str, Any] = cast(dict[str, Any], data.get("info") or {})
        error_raw = info.get("error")
        if isinstance(error_raw, dict):
            error_data: dict[str, Any] = cast(dict[str, Any], error_raw)
            error_payload: dict[str, Any] = cast(dict[str, Any], error_data.get("data") or {})
            message = str(error_payload.get("message") or error_data.get("name"))
            if error_payload.get("statusCode") == 429:
                raise ProviderThrottlingError(
                    "opencode reported rate limiting",
                    technical_context=message,
                    retry_after=None,
                )
            raise ProviderResponseError("opencode provider error", technical_context=message[:300])
        parts_raw = data.get("parts")
        response_parts: list[dict[str, Any]] = (
            cast(list[dict[str, Any]], parts_raw) if isinstance(parts_raw, list) else []
        )
        text_parts: list[TextPart] = []
        for part in response_parts:
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                text_parts.append(TextPart(text=str(part["text"])))
        tokens_raw = info.get("tokens")
        tokens: dict[str, Any] = (
            cast(dict[str, Any], tokens_raw) if isinstance(tokens_raw, dict) else {}
        )
        usage = TokenUsage(
            input_tokens=int(tokens.get("input", 0) or 0),
            output_tokens=int(tokens.get("output", 0) or 0),
            source=UsageSource.PROVIDER,
        )
        reasoning_tokens = _reasoning_tokens(tokens)
        reasoning_items = tuple(
            dict(part)
            for part in response_parts
            if part.get("type") in {"reasoning", "reasoning_summary"}
        )
        reasoning_summary = (
            "\n".join(
                str(item.get("text"))
                for item in reasoning_items
                if isinstance(item.get("text"), str)
            )
            or None
        )
        telemetry = ReasoningTelemetry(
            provider=self._provider_id,
            model=str(info.get("modelID") or request.model.model),
            usage=tokens,
            reasoning_tokens=reasoning_tokens,
            reasoning_items=reasoning_items,
            reasoning_summary=reasoning_summary,
            availability=ReasoningAvailability(
                reasoning_tokens=reasoning_tokens is not None,
                reasoning_items=bool(reasoning_items),
                reasoning_summary=reasoning_summary is not None,
            ),
            wire_fidelity=WireFidelity.PARTIAL,
            provider_metadata=info,
        )
        return ProviderResult(
            response=NormalizedResponse(
                content_parts=tuple(text_parts),
                stop_reason=StopReason(canonical="end_turn"),
                model_requested=request.model,
                model_reported=str(info.get("modelID") or request.model.model),
                request_id=str(info.get("parentID") or ""),
                usage=usage,
                started_at=started,
                finished_at=utc_now(),
                adapter_version=self.backend_version,
                wire_fidelity=WireFidelity.PARTIAL,
                warnings=("opencode system prompt contributes to input tokens",),
            ),
            wire_request={
                "model": {
                    "providerID": self._provider_id,
                    "modelID": request.model.model,
                },
                "parts": parts,
            },
            wire_response=data,
            reasoning_telemetry=telemetry,
            wire_fidelity=WireFidelity.PARTIAL,
        )

    async def _dispose_session(self, session_id: str) -> None:
        import contextlib

        with contextlib.suppress(httpx.HTTPError):
            await self._client.delete(f"/session/{session_id}")

    async def close(self) -> None:
        await self._client.aclose()


def _reasoning_tokens(tokens: dict[str, Any]) -> int | None:
    for key in ("reasoning", "reasoning_tokens", "reasoningTokens"):
        value = tokens.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    details_raw = tokens.get("details")
    details = cast(dict[str, Any], details_raw) if isinstance(details_raw, dict) else {}
    if details:
        value = details.get("reasoning_tokens") or details.get("reasoningTokens")
        if isinstance(value, int) and value >= 0:
            return value
    return None
