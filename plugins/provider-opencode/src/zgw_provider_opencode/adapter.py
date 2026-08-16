"""opencode headless-server adapter.

The opencode server (``opencode serve``) exposes a session/message HTTP API.
This adapter maps ONE canonical ModelRequest to ONE opencode session+message,
so calls stay isolated: no hidden cross-call context, no agent loop, no
fallback. Usage reported by opencode is recorded with ``source=provider``;
cost stays ``unknown`` (GATE-009). Errors map to the typed provider taxonomy.
"""

from __future__ import annotations

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
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._provider_id = provider_id
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
                    Capability.USAGE_REPORTING,
                }
            ),
            known_models=(),
            limitations=(
                f"opencode server at {self._base_url}",
                "one session per call (context isolation)",
                "no tool_calling via this adapter in v0.1",
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
        session_id = await self._create_session(request.model)
        try:
            return await self._prompt(session_id, request, context, started)
        finally:
            await self._dispose_session(session_id)

    async def _create_session(self, model: ModelRef) -> str:
        try:
            response = await self._client.post(
                "/session",
                json={"title": "zugzwang-call"},
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
        return session_id

    async def _prompt(
        self,
        session_id: str,
        request: ModelRequest,
        context: CallContext,
        started: Any,
    ) -> ProviderResult:
        parts: list[dict[str, str]] = []
        for message in request.messages:
            text = "\n".join(part.text for part in message.parts if isinstance(part, TextPart))
            parts.append({"type": "text", "text": text})
        try:
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
        if response.status_code == 429:
            raise ProviderThrottlingError(
                "opencode rate limited (429)", technical_context=self._base_url
            )
        if response.status_code >= 400:
            raise ProviderServerError(
                f"opencode message call failed ({response.status_code})",
                technical_context=response.text[:200],
            )
        data: dict[str, Any] = cast(dict[str, Any], response.json())
        info: dict[str, Any] = cast(dict[str, Any], data.get("info") or {})
        error_raw = info.get("error")
        if isinstance(error_raw, dict):
            error_data: dict[str, Any] = cast(dict[str, Any], error_raw)
            error_payload: dict[str, Any] = cast(dict[str, Any], error_data.get("data") or {})
            message = str(error_payload.get("message") or error_data.get("name"))
            if error_payload.get("statusCode") == 429:
                raise ProviderThrottlingError(
                    "opencode reported rate limiting", technical_context=message
                )
            raise ProviderResponseError("opencode provider error", technical_context=message[:300])
        text_parts: list[TextPart] = []
        for part in cast(list[dict[str, Any]], data.get("parts") or []):
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                text_parts.append(TextPart(text=str(part["text"])))
        tokens: dict[str, Any] = cast(dict[str, Any], info.get("tokens") or {})
        usage = TokenUsage(
            input_tokens=int(tokens.get("input", 0) or 0),
            output_tokens=int(tokens.get("output", 0) or 0),
            source=UsageSource.PROVIDER,
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
            )
        )

    async def _dispose_session(self, session_id: str) -> None:
        import contextlib

        with contextlib.suppress(httpx.HTTPError):
            await self._client.delete(f"/session/{session_id}")

    async def close(self) -> None:
        await self._client.aclose()
