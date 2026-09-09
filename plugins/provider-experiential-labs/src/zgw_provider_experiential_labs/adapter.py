"""Experiential Labs gateway adapter (OpenAI Chat Completions wire).

Routes ONE canonical inference call to ``POST /v1/chat/completions`` on the
Experiential Labs gateway (default ``https://api.experientiallabs.ai/v1``) with
an ``xpl_`` bearer key. The credential arrives as an ``env:`` reference and is
resolved by the runtime — it never lands in manifests or artifacts.

Gateway facts (ZGW-0106, from the platform docs — /docs/errors, /docs/models,
/api/models/<slug> — plus live probes against ``deepseek-v4-flash``):

- **reasoning_effort crashes the deepseek-v4-flash lane.** The catalog entry
  for the lane answers ``capabilities.supports_reasoning: false``, and a live
  request carrying ``reasoning_effort`` returns an instant bodyless
  Cloudflare 502 (probed 2026-09-08/09) even though the prose docs once
  claimed effort "is served, never rejected". The adapter retries once
  without the field and then REMEMBERS the rejection per model for the
  lifetime of the backend, so later calls never pay the dead round-trip.
  Every drop is disclosed in result warnings.
- **Official retry policy** (their /docs/errors): retry 429/500/502/503/504
  with exponential backoff; never blindly retry 400/401/403/409;
  ``insufficient_quota`` is not transient. The adapter therefore backs off
  and retries bounded server errors (default 2 extra wire calls) while
  leaving timeouts fail-closed (ZGZ-PROVIDER_TRANSPORT-002, no blind retry).
- **Idempotency-Key**: gateway delivery is at-least-once — an ambiguous
  network failure that is retried can dispatch and bill the provider twice.
  Every wire call carries ``Idempotency-Key`` derived from the kernel
  attempt identity, so a wire-level retry REPLAYS the original result
  instead of running again. ``409 idempotency_replay_unavailable`` triggers
  exactly one resend under a fresh key (their documented recovery).
- ``seed`` is advertised in the catalog but the gateway answers 400
  ``unsupported_parameter`` on this route, so the adapter strips it before
  the wire call and records the drop in the result warnings.
- ``usage.cost`` is stamped inline on every reply (BYOK settles 0 with
  ``is_byok``). GATE-009 keeps billed cost out of the canonical usage, so
  cost is persisted only inside the raw wire response evidence.
- ``insufficient_quota`` / ``insufficient_credits`` (429) mean retrying is
  pointless without operator action: they surface as ``ProviderResponseError``,
  while throttled routes (``unavailable_route`` / ``gateway_overloaded``)
  surface as ``ProviderThrottlingError`` for the runtime backoff.
- DeepSeek lanes expose plaintext ``reasoning_content`` on the assistant
  message; it is preserved as the reasoning summary (never claimed as CoT).

Evidence contract: the full wire request/response ride the ``ProviderResult``;
the gateway's ignored-parameters disclosure is kept verbatim.
"""

from __future__ import annotations

import asyncio
import json
import uuid
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

_THROTTLE_CODES = {
    "unavailable_route",
    "gateway_overloaded",
    "all_routes_failed",
    "backend_unavailable",
    "gateway_draining",
    "deadline_exceeded",
    "internal_error",
}
_NO_RETRY_QUOTA_CODES = {
    "insufficient_quota",
    "insufficient_credits",
    "org_under_review",
    "model_requires_payment",
    "model_requires_purchase",
    "free_limit_reached",
    "free_tier_requires_payment",
    "promo_byok_only",
}
# HTTP statuses the gateway's own docs say to retry with backoff
# (500 internal_error, 502 provider_internal/all_routes_failed/
# provider_output_too_large, 503 gateway_draining, 504 deadline_exceeded).
_SERVER_RETRY_STATUSES = {500, 502, 503, 504}

_KNOWN_MODEL = "deepseek-v4-flash"


class ExperientialLabsBackend:
    """One inference call -> one Chat Completions request on the XPL gateway."""

    backend_id = "provider.experiential_labs"
    backend_version = "0.2.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        base_url: str = "https://api.experientiallabs.ai/v1",
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        reasoning_effort: str | None = None,
        default_max_output_tokens: int | None = None,
        server_retries: int = 2,
        backoff_base: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._reasoning_effort = reasoning_effort
        self._default_max_output_tokens = default_max_output_tokens
        self._server_retries = max(0, int(server_retries))
        self._backoff_base = max(0.0, float(backoff_base))
        # models whose lane rejected reasoning_effort (learned, in-process)
        self._effort_rejected_models: set[str] = set()
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
                    Capability.REASONING_CONTROL,
                }
            ),
            known_models=(
                ModelRef(
                    backend=self.backend_id,
                    provider="experiential-cloud",
                    model=_KNOWN_MODEL,
                ),
            ),
            limitations=(
                f"gateway={self._base_url}",
                "seed is stripped (gateway rejects it with unsupported_parameter)"
                " and recorded in result warnings",
                "reasoning_effort is dropped for lanes that reject it"
                " (deepseek-v4-flash answers an instant 502 to the field);"
                " the drop is disclosed verbatim in result warnings",
                "bounded backoff retry on 500/502/503/504 per the gateway's"
                " documented policy; Idempotency-Key is always sent so wire"
                " retries replay instead of re-billing",
                "usage.cost is wire evidence only (GATE-009: billed cost unknown)",
                "single assistant tool call per turn on deepseek-v4-flash"
                " (supports_parallel_tool_calls=false)",
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
        self._require_supported_parts(request)
        seed_dropped = request.inference.seed is not None
        model_id = request.model.model
        suppress_effort = model_id in self._effort_rejected_models
        payload = self._lower_request(request, suppress_effort=suppress_effort)
        idempotency_key = self._idempotency_key(context)
        wire_retries = 0
        effort_dropped = False
        replay_resent = False

        while True:
            response = await self._post_chat(payload, idempotency_key)
            if (
                "reasoning_effort" in payload
                and response.status_code >= 400
                and response.status_code != 429
                and _looks_like_effort_rejection(response)
            ):
                # The lane rejects the field itself (instant bodyless 502 or
                # 400 unsupported_parameter): retry immediately without it and
                # remember the drop for this backend — a parameter problem is
                # not an outage, so no backoff here.
                payload = {k: v for k, v in payload.items() if k != "reasoning_effort"}
                self._effort_rejected_models.add(model_id)
                effort_dropped = True
                continue
            if response.status_code == 409 and not replay_resent:
                error_code = self._error_code(response)
                if error_code == "idempotency_replay_unavailable":
                    # their documented recovery: resend under a fresh key
                    idempotency_key = f"{idempotency_key}-r1"
                    replay_resent = True
                    continue
            if (
                response.status_code in _SERVER_RETRY_STATUSES
                and wire_retries < self._server_retries
            ):
                wire_retries += 1
                await asyncio.sleep(
                    self._retry_after_seconds(response)
                    or self._backoff_base * (2 ** (wire_retries - 1))
                )
                continue
            break

        try:
            raw_body = response.json()
            wire_response: dict[str, Any] = (
                cast(dict[str, Any], raw_body) if isinstance(raw_body, dict) else {}
            )
        except (ValueError, json.JSONDecodeError):
            wire_response = {}

        if response.status_code == 429:
            raise self._throttle_or_quota_error(response, wire_response)
        if response.status_code == 401:
            raise ProviderConnectionError(
                "experiential labs rejected the key (401 invalid_key)",
                technical_context=self._base_url,
            )
        if response.status_code == 403:
            raise ProviderResponseError(
                "experiential labs refused the model (403 model_not_granted)",
                technical_context=str(wire_response.get("error", ""))[:300],
            )
        if response.status_code >= 500:
            raise ProviderServerError(
                f"experiential labs server error ({response.status_code})"
                f" after {wire_retries} bounded retry(ies)",
                technical_context=self._base_url,
            )
        if response.status_code >= 400:
            raise ProviderResponseError(
                f"experiential labs error ({response.status_code}): {response.text[:200]}",
                technical_context=self._base_url,
            )
        if wire_response.get("error"):
            raise ProviderResponseError(
                "experiential labs returned an error body",
                technical_context=str(wire_response["error"])[:300],
            )

        warnings: list[str] = []
        if wire_retries:
            warnings.append(
                f"wire retried {wire_retries}x with backoff on server errors"
                " (gateway-documented policy; Idempotency-Key made the retries replay)"
            )
        normalized = self._raise_response(
            request,
            wire_response,
            started,
            seed_dropped=seed_dropped,
            effort_dropped=effort_dropped,
            extra_warnings=warnings,
        )
        return ProviderResult(
            response=normalized,
            wire_request=payload,
            wire_response=wire_response,
            reasoning_telemetry=self._reasoning_telemetry(request, wire_response),
            wire_fidelity=WireFidelity.FULL,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _idempotency_key(self, context: CallContext) -> str:
        """Stable per kernel attempt: wire retries replay, never re-dispatch."""
        if context.idempotency_key:
            return context.idempotency_key
        if context.attempt_id:
            return f"zgw-{context.attempt_id}"
        return f"zgw-{uuid.uuid4()}"

    def _error_code(self, response: httpx.Response) -> str:
        try:
            raw_body = response.json()
        except (ValueError, json.JSONDecodeError):
            return ""
        body: dict[str, Any] = cast(dict[str, Any], raw_body) if isinstance(raw_body, dict) else {}
        raw = body.get("error")
        error: dict[str, Any] = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        return str(error.get("code") or "")

    async def _post_chat(self, payload: dict[str, Any], idempotency_key: str) -> httpx.Response:
        try:
            return await self._client.post(
                "/chat/completions",
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
        except httpx.TimeoutException as exc:
            # fail-closed: an ambiguous timeout is never retried here
            raise ProviderTimeoutError(
                "experiential labs call timed out", technical_context=self._base_url
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError(
                "experiential labs transport failure", technical_context=str(exc)
            ) from exc

    def _retry_after_seconds(self, response: httpx.Response) -> float | None:
        raw_header = response.headers.get("retry-after")
        if raw_header is None:
            return None
        try:
            return max(0.0, float(raw_header))
        except (TypeError, ValueError):
            return None

    def _require_supported_parts(self, request: ModelRequest) -> None:
        needs_image = any(
            isinstance(part, ImagePart) for message in request.messages for part in message.parts
        )
        if needs_image:
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

    def _lower_request(self, request: ModelRequest, *, suppress_effort: bool) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            role = self._role(message.role)
            text_parts = [p.text for p in message.parts if isinstance(p, TextPart)]
            json_parts = [
                json.dumps(p.data, ensure_ascii=False, sort_keys=True)
                for p in message.parts
                if isinstance(p, JsonDataPart)
            ]
            call_parts = [p for p in message.parts if isinstance(p, ToolCallPart)]
            result_parts = [p for p in message.parts if isinstance(p, ToolResultPart)]
            if call_parts or result_parts:
                if message.role is MessageRole.TOOL:
                    if call_parts or text_parts or json_parts:
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
            messages.append({"role": role, "content": "\n".join(text_parts + json_parts)})
        payload: dict[str, Any] = {
            "model": request.model.model,
            "messages": messages,
        }
        max_output_tokens = request.inference.max_output_tokens or self._default_max_output_tokens
        if max_output_tokens:
            payload["max_tokens"] = max_output_tokens
        if request.inference.temperature is not None:
            payload["temperature"] = request.inference.temperature
        # seed is advertised in the catalog but rejected on this route
        # (400 unsupported_parameter) — stripped, disclosed in warnings.
        if request.inference.stop:
            payload["stop"] = list(request.inference.stop)
        if self._reasoning_effort and not suppress_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters or {"type": "object"},
                    },
                }
                for tool in request.tools
            ]
        if (
            request.output_constraint.format == "json_object"
            or request.output_constraint.format == "json_schema"
        ):
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _raise_response(
        self,
        request: ModelRequest,
        body: dict[str, Any],
        started: Any,
        *,
        seed_dropped: bool,
        effort_dropped: bool = False,
        extra_warnings: list[str] | None = None,
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
        warnings: list[str] = list(extra_warnings or [])
        if seed_dropped:
            warnings.append(
                "request seed stripped: the gateway rejects seed on this route"
                " (400 unsupported_parameter)"
            )
        if effort_dropped:
            warnings.append(
                "reasoning_effort stripped: this model lane rejects the field"
                " (instant 502); it is suppressed for the rest of this backend"
                " and was retried once without it"
            )
        ignored = body.get("x-experiential-ignored-parameters")
        if isinstance(ignored, list) and ignored:
            ignored_items = cast(list[Any], ignored)
            names = ", ".join(str(item) for item in ignored_items)
            warnings.append(f"gateway ignored parameters: {names}")
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
            warnings=tuple(warnings),
        )

    def _reasoning_telemetry(
        self, request: ModelRequest, body: dict[str, Any]
    ) -> ReasoningTelemetry:
        """Preserve DeepSeek-lane reasoning_content without calling it CoT."""
        summaries: list[str] = []
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
        return ReasoningTelemetry(
            provider="experiential-cloud",
            model=str(body.get("model") or request.model.model),
            reasoning_effort=self._reasoning_effort,
            usage=usage_data,
            reasoning_items=(),
            reasoning_summary="\n".join(summaries) if summaries else None,
            availability=ReasoningAvailability(
                reasoning_tokens=False,
                reasoning_items=False,
                reasoning_summary=bool(summaries),
            ),
            wire_fidelity=WireFidelity.FULL,
            provider_metadata={"gateway": self._base_url},
        )

    def _throttle_or_quota_error(
        self, response: httpx.Response, body: dict[str, Any]
    ) -> ProviderResponseError | ProviderThrottlingError:
        error_raw = body.get("error")
        error: dict[str, Any] = (
            cast(dict[str, Any], error_raw) if isinstance(error_raw, dict) else {}
        )
        code = str(error.get("code") or "")
        detail = str(error.get("message") or response.text[:200])
        if code in _NO_RETRY_QUOTA_CODES:
            return ProviderResponseError(
                f"experiential labs quota exhausted ({code}): {detail[:200]}",
                technical_context=self._base_url,
            )
        return ProviderThrottlingError(
            f"experiential labs throttled ({code or '429'}): {detail[:200]}",
            technical_context=self._base_url,
            retry_after=self._retry_after_seconds(response),
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


def _looks_like_effort_rejection(response: httpx.Response) -> bool:
    """True when the failure plausibly comes from the reasoning_effort field.

    Two observed signatures (probed 2026-09-08/09): an instant bodyless
    Cloudflare 502 ("error code: 502") from the deepseek-v4-flash lane, and
    the documented 400 ``unsupported_parameter`` for fields a route rejects.
    A 429 is excluded — quota/throttling has its own path — and a 401/403 is
    an auth/grant problem, never the field.
    """
    if response.status_code in (401, 403, 429):
        return False
    return response.status_code >= 400
