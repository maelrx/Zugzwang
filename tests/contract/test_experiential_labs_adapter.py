"""Contract tests for the Experiential Labs provider adapter.

Runs offline against an httpx MockTransport: no network, no secrets (ADR-031).
The canned bodies mirror the live gateway probes (ZGW-0106): OpenAI chat
completion envelope with inline usage.cost, tool_calls shape, reasoning_content
on the assistant message, and the x-experiential-ignored-parameters disclosure.
"""

from __future__ import annotations

import json

import httpx
import pytest

from zugzwang_core.domain.errors import (
    CapabilityMissingError,
    ProviderConnectionError,
    ProviderResponseError,
    ProviderServerError,
    ProviderThrottlingError,
)
from zugzwang_core.domain.money import UsageSource
from zugzwang_core.ports.model import (
    CallContext,
    Capability,
    ImagePart,
    InferenceSettings,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolDefinition,
)

from .contract_suite import run_model_backend_contract


def _chat_body(
    content: str | None = "e2e4",
    *,
    model: str = "deepseek-v4-flash",
    finish: str = "stop",
    usage: dict[str, object] | None = None,
    reasoning_content: str | None = None,
    tool_calls: list[dict[str, object]] | None = None,
    ignored: list[str] | None = None,
) -> dict[str, object]:
    message: dict[str, object] = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    body: dict[str, object] = {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "created": 1788916808,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": usage
        or {
            "prompt_tokens": 11,
            "completion_tokens": 4,
            "total_tokens": 15,
            "cost": 0.0,
            "is_byok": False,
        },
    }
    if ignored is not None:
        body["x-experiential-ignored-parameters"] = ignored
    return body


def _backend(handler: object, **kwargs: object) -> object:
    from zgw_provider_experiential_labs.adapter import ExperientialLabsBackend

    return ExperientialLabsBackend(
        base_url="http://mock.local/v1",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def _request(**overrides: object) -> tuple[ModelRequest, CallContext]:
    model = ModelRef(
        backend="provider.experiential_labs",
        provider="experiential-cloud",
        model="deepseek-v4-flash",
    )
    fields: dict[str, object] = {
        "model": model,
        "messages": (Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
    }
    fields.update(overrides)
    return ModelRequest(**fields), CallContext(run_id="run_test")  # type: ignore[arg-type]


@pytest.mark.contract
@pytest.mark.asyncio
class TestExperientialLabsAdapter:
    async def test_passes_model_contract(self) -> None:
        backend = _backend(lambda _: httpx.Response(200, json=_chat_body()))
        await run_model_backend_contract(backend)  # type: ignore[arg-type]
        await backend.close()  # type: ignore[attr-defined]

    async def test_usage_and_model_reported(self) -> None:
        backend = _backend(lambda _: httpx.Response(200, json=_chat_body()))
        request, context = _request()
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert result.response.usage.source is UsageSource.PROVIDER
        assert result.response.usage.input_tokens == 11
        assert result.response.usage.output_tokens == 4
        assert result.response.model_reported == "deepseek-v4-flash"
        assert result.response.stop_reason.canonical == "end_turn"
        assert result.wire_fidelity.value == "full"
        await backend.close()  # type: ignore[attr-defined]

    async def test_tool_call_roundtrip(self) -> None:
        tool_calls = [
            {
                "id": "chatcmpl-tool-1",
                "type": "function",
                "function": {
                    "name": "board_expand",
                    "arguments": json.dumps({"node_id": "root"}),
                },
            }
        ]
        backend = _backend(
            lambda _: httpx.Response(
                200, json=_chat_body(None, finish="tool_calls", tool_calls=tool_calls)
            )
        )
        request, context = _request(
            tools=(
                ToolDefinition(
                    name="board_expand",
                    description="Expand a node",
                    parameters={"type": "object"},
                ),
            )
        )
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert result.response.stop_reason.canonical == "tool_calls"
        assert len(result.response.tool_calls) == 1
        call = result.response.tool_calls[0]
        assert isinstance(call, ToolCallPart)
        assert call.tool_name == "board_expand"
        assert call.arguments == {"node_id": "root"}
        await backend.close()  # type: ignore[attr-defined]

    async def test_seed_stripped_with_warning(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler)
        request, context = _request(inference=InferenceSettings(seed=20260908))
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert "seed" not in seen["body"]  # type: ignore[index]
        assert any("seed" in w for w in result.response.warnings)
        await backend.close()  # type: ignore[attr-defined]

    async def test_reasoning_effort_forwarded(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler, reasoning_effort="medium")
        request, context = _request()
        await backend.infer(request, context)  # type: ignore[attr-defined]
        assert seen["body"]["reasoning_effort"] == "medium"  # type: ignore[index]
        await backend.close()  # type: ignore[attr-defined]

    async def test_effort_rejection_retries_once_without_field(self) -> None:
        bodies: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            bodies.append(body)
            if "reasoning_effort" in body:
                return httpx.Response(502, text="error code: 502")
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler, reasoning_effort="low")
        request, context = _request()
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert len(bodies) == 2
        assert "reasoning_effort" not in bodies[1]
        assert result.response.stop_reason.canonical == "end_turn"
        assert any("reasoning_effort" in w for w in result.response.warnings)
        assert result.wire_request.get("reasoning_effort") is None
        await backend.close()  # type: ignore[attr-defined]

    async def test_quota_429_with_effort_does_not_retry_without_field(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                429,
                json={"error": {"message": "spent", "code": "insufficient_quota"}},
            )

        backend = _backend(handler, reasoning_effort="low")
        request, context = _request()
        with pytest.raises(ProviderResponseError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        assert calls == 1
        await backend.close()  # type: ignore[attr-defined]

    async def test_reasoning_content_becomes_summary(self) -> None:
        backend = _backend(
            lambda _: httpx.Response(200, json=_chat_body("ok", reasoning_content="thinking trace"))
        )
        request, context = _request()
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert result.reasoning_telemetry.reasoning_summary == "thinking trace"
        assert result.reasoning_telemetry.availability.reasoning_summary is True
        await backend.close()  # type: ignore[attr-defined]

    async def test_ignored_params_disclosed_as_warning(self) -> None:
        backend = _backend(lambda _: httpx.Response(200, json=_chat_body(ignored=["temperature"])))
        request, context = _request()
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert any("temperature" in w for w in result.response.warnings)
        await backend.close()  # type: ignore[attr-defined]

    async def test_image_refused_before_wire(self) -> None:
        backend = _backend(lambda _: httpx.Response(200, json=_chat_body()))
        request, context = _request(
            messages=(
                Message(
                    role=MessageRole.USER,
                    parts=(
                        ImagePart(
                            mime="image/png",
                            width=1,
                            height=1,
                            content_sha256="0" * 64,
                            data_base64="AAAA",
                        ),
                    ),
                ),
            )
        )
        with pytest.raises(CapabilityMissingError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        await backend.close()  # type: ignore[attr-defined]

    async def test_seed_capability_missing(self) -> None:
        backend = _backend(lambda _: httpx.Response(200, json=_chat_body()))
        report = await backend.inspect_capabilities(  # type: ignore[attr-defined]
            ModelRef(
                backend="provider.experiential_labs",
                provider="experiential-cloud",
                model="deepseek-v4-flash",
            ),
            required=frozenset({Capability.SEED}),
        )
        assert Capability.SEED in report.missing_required
        await backend.close()  # type: ignore[attr-defined]

    async def test_quota_error_is_not_retried(self) -> None:
        body = {
            "error": {
                "message": "free tier allowance spent",
                "type": "rate_limit_error",
                "code": "insufficient_quota",
            }
        }
        backend = _backend(lambda _: httpx.Response(429, json=body))
        request, context = _request()
        with pytest.raises(ProviderResponseError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        await backend.close()  # type: ignore[attr-defined]

    async def test_throttled_route_retries(self) -> None:
        body = {
            "error": {
                "message": "no healthy route",
                "type": "server_error",
                "code": "unavailable_route",
            }
        }
        backend = _backend(lambda _: httpx.Response(429, json=body, headers={"retry-after": "3"}))
        request, context = _request()
        with pytest.raises(ProviderThrottlingError) as excinfo:
            await backend.infer(request, context)  # type: ignore[attr-defined]
        assert excinfo.value.retry_after == 3.0
        await backend.close()  # type: ignore[attr-defined]

    async def test_unauthorized_key_is_connection_error(self) -> None:
        body = {"error": {"message": "bad key", "code": "invalid_key"}}
        backend = _backend(lambda _: httpx.Response(401, json=body))
        request, context = _request()
        with pytest.raises(ProviderConnectionError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        await backend.close()  # type: ignore[attr-defined]

    async def test_server_error_maps(self) -> None:
        backend = _backend(lambda _: httpx.Response(502, text="bad gateway"))
        request, context = _request()
        with pytest.raises(ProviderServerError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        await backend.close()  # type: ignore[attr-defined]

    async def test_server_5xx_retries_with_backoff_then_succeeds(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(502, text="error code: 502")
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler, backoff_base=0.01)
        request, context = _request()
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert calls == 2
        assert any("retried 1x" in w for w in result.response.warnings)
        await backend.close()  # type: ignore[attr-defined]

    async def test_server_5xx_exhaustion_counts_wire_retries(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(503, text="draining")

        backend = _backend(handler, server_retries=2, backoff_base=0.01)
        request, context = _request()
        with pytest.raises(ProviderServerError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        assert calls == 3  # 1 original + 2 bounded retries
        await backend.close()  # type: ignore[attr-defined]

    async def test_idempotency_key_stable_across_wire_retries(self) -> None:
        keys: list[str] = []
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            keys.append(request.headers.get("Idempotency-Key") or "")
            if calls == 1:
                return httpx.Response(502, text="error code: 502")
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler, backoff_base=0.01)
        request, context = _request()
        _ = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert len(keys) == 2
        assert keys[0] == keys[1] and keys[0] != ""
        await backend.close()  # type: ignore[attr-defined]

    async def test_idempotency_replay_unavailable_resends_fresh_key(self) -> None:
        keys: list[str] = []
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            keys.append(request.headers.get("Idempotency-Key") or "")
            if calls == 1:
                return httpx.Response(
                    409,
                    json={
                        "error": {
                            "message": "original keyed result is gone",
                            "code": "idempotency_replay_unavailable",
                        }
                    },
                )
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler)
        request, context = _request()
        result = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert calls == 2
        assert keys[1] == keys[0] + "-r1"
        assert result.response.text() == "e2e4"
        await backend.close()  # type: ignore[attr-defined]

    async def test_effort_rejection_remembered_across_calls(self) -> None:
        calls = 0
        bodies: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            body = json.loads(request.content.decode("utf-8"))
            bodies.append(body)
            if "reasoning_effort" in body:
                return httpx.Response(502, text="error code: 502")
            return httpx.Response(200, json=_chat_body())

        backend = _backend(handler, reasoning_effort="low")
        request, context = _request()
        _ = await backend.infer(request, context)  # type: ignore[attr-defined]
        _ = await backend.infer(request, context)  # type: ignore[attr-defined]
        assert calls == 3  # first call: 502 + fallback; second call: straight 200
        assert all("reasoning_effort" not in b for b in bodies[1:])
        await backend.close()  # type: ignore[attr-defined]

    async def test_403_is_not_treated_as_effort_rejection(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                403,
                json={"error": {"message": "not granted", "code": "model_not_granted"}},
            )

        backend = _backend(handler, reasoning_effort="low")
        request, context = _request()
        with pytest.raises(ProviderResponseError):
            await backend.infer(request, context)  # type: ignore[attr-defined]
        assert calls == 1  # no effort fallback on an auth/grant failure
        await backend.close()  # type: ignore[attr-defined]
