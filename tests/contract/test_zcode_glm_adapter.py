"""Contract tests for the ZCode Coding Plan (GLM) provider adapter.

Runs offline against an httpx MockTransport: no network, no secrets (ADR-031).
"""

from __future__ import annotations

import json

import httpx
import pytest

from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    TextPart,
)

from .contract_suite import run_model_backend_contract


def _messages_response(
    blocks: list[dict[str, object]],
    *,
    model: str = "glm-5.3-flash",
    stop: str = "end_turn",
    usage: dict[str, object] | None = None,
) -> httpx.Response:
    body: dict[str, object] = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": blocks,
        "stop_reason": stop,
        "usage": usage or {"input_tokens": 18, "output_tokens": 9},
    }
    return httpx.Response(200, json=body)


def _text_block(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def _request() -> tuple[ModelRequest, CallContext]:
    model = ModelRef(
        backend="provider.zcode_glm", provider="zcode-coding-plan", model="GLM-5.3-Flash"
    )
    request = ModelRequest(
        model=model,
        messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
    )
    return request, CallContext(run_id="run_test")


@pytest.mark.contract
@pytest.mark.asyncio
class TestZCodeGlmAdapter:
    async def test_passes_model_contract(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/v1/messages")
            return _messages_response([_text_block("e2e4")])

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(handler),
        )
        await run_model_backend_contract(backend)
        await backend.close()

    async def test_usage_and_model_reported(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.domain.money import UsageSource

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(
                lambda _: _messages_response(
                    [_text_block("ok")],
                    usage={"input_tokens": 21, "output_tokens": 4},
                )
            ),
        )
        request, context = _request()
        result = await backend.infer(request, context)
        assert result.response.usage.source is UsageSource.PROVIDER
        assert result.response.usage.input_tokens == 21
        assert result.response.model_reported == "glm-5.3-flash"
        assert result.response.stop_reason.canonical == "end_turn"
        assert result.wire_fidelity.value == "full"
        await backend.close()

    async def test_tool_use_roundtrip(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.ports.model import ToolCallPart

        tool_use = {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "board_finalize",
            "input": {"node_id": "root", "action_id": "e2e4"},
        }
        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(
                lambda _: _messages_response([tool_use], stop="tool_use")
            ),
        )
        request, context = _request()
        result = await backend.infer(request, context)
        assert result.response.stop_reason.canonical == "tool_calls"
        assert len(result.response.tool_calls) == 1
        call = result.response.tool_calls[0]
        assert isinstance(call, ToolCallPart)
        assert call.tool_call_id == "toolu_1"
        assert call.tool_name == "board_finalize"
        assert call.arguments["action_id"] == "e2e4"
        await backend.close()

    async def test_lowering_tools_system_and_thinking(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
            ToolCallPart,
            ToolDefinition,
            ToolResultPart,
        )

        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            return _messages_response([_text_block("ok")])

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            reasoning_effort="low",
            transport=httpx.MockTransport(handler),
        )
        model = ModelRef(
            backend="provider.zcode_glm", provider="zcode-coding-plan", model="GLM-5.3-Flash"
        )
        request = ModelRequest(
            model=model,
            messages=(
                Message(role=MessageRole.SYSTEM, parts=(TextPart(text="be careful"),)),
                Message(role=MessageRole.USER, parts=(TextPart(text="position"),)),
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=(
                        ToolCallPart(
                            tool_call_id="toolu_9",
                            tool_name="board_observe",
                            arguments={"node_id": "root"},
                        ),
                    ),
                ),
                Message(
                    role=MessageRole.TOOL,
                    parts=(
                        ToolResultPart(
                            tool_call_id="toolu_9",
                            tool_name="board_observe",
                            content="fen: ...",
                        ),
                    ),
                ),
            ),
            tools=(
                ToolDefinition(
                    name="board_observe", description="observe", parameters={"type": "object"}
                ),
            ),
        )
        await backend.infer(request, CallContext(run_id="run_test"))
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["system"] == "be careful"
        assert body["max_tokens"] == 8192
        assert body["thinking"] == {"type": "enabled", "budget_tokens": 1024}
        assert body["tools"][0]["name"] == "board_observe"
        roles = [m["role"] for m in body["messages"]]
        assert roles == ["user", "assistant", "user"]
        tool_use_block = body["messages"][1]["content"][0]
        assert tool_use_block["type"] == "tool_use"
        tool_result_block = body["messages"][2]["content"][0]
        assert tool_result_block["type"] == "tool_result"
        assert tool_result_block["tool_use_id"] == "toolu_9"
        await backend.close()

    async def test_thinking_budget_bumps_max_tokens(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.ports.model import (
            CallContext,
            InferenceSettings,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            return _messages_response([_text_block("ok")])

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            reasoning_effort="high",
            transport=httpx.MockTransport(handler),
        )
        request = ModelRequest(
            model=ModelRef(
                backend="provider.zcode_glm", provider="zcode-coding-plan", model="GLM-5.3-Flash"
            ),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
            inference=InferenceSettings(max_output_tokens=2048),
        )
        await backend.infer(request, CallContext(run_id="run_test"))
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["max_tokens"] == 8192 + 1024
        assert body["thinking"]["budget_tokens"] == 8192
        await backend.close()

    async def test_thinking_telemetry_preserved(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        blocks: list[dict[str, object]] = [
            {"type": "thinking", "thinking": "check captures first", "signature": "sig"},
            _text_block("e2e4"),
        ]
        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            reasoning_effort="low",
            transport=httpx.MockTransport(lambda _: _messages_response(blocks)),
        )
        request, context = _request()
        result = await backend.infer(request, context)
        telemetry = result.reasoning_telemetry
        assert telemetry is not None
        assert telemetry.reasoning_items[0]["thinking"] == "check captures first"
        assert telemetry.reasoning_summary == "check captures first"
        assert telemetry.availability.reasoning_items is True
        await backend.close()

    async def test_429_is_throttling_with_retry_after_context(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.domain.errors import ProviderThrottlingError

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    429, json={"error": {"message": "slow down"}}, headers={"retry-after": "7"}
                )
            ),
        )
        request, context = _request()
        with pytest.raises(ProviderThrottlingError) as excinfo:
            await backend.infer(request, context)
        assert "retry_after=7.0s" in (excinfo.value.technical_context or "")
        await backend.close()

    async def test_500_is_server_error(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.domain.errors import ProviderServerError

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(500, json={"error": {"message": "boom"}})
            ),
        )
        request, context = _request()
        with pytest.raises(ProviderServerError):
            await backend.infer(request, context)
        await backend.close()

    async def test_timeout_is_timeout_error(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.domain.errors import ProviderTimeoutError

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(handler),
        )
        request, context = _request()
        with pytest.raises(ProviderTimeoutError):
            await backend.infer(request, context)
        await backend.close()

    async def test_error_body_is_response_error(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        from zugzwang_core.domain.errors import ProviderResponseError

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"type": "error", "error": {"type": "overloaded_error"}}
                )
            ),
        )
        request, context = _request()
        with pytest.raises(ProviderResponseError):
            await backend.infer(request, context)
        await backend.close()

    async def test_api_key_never_in_wire_request(self) -> None:
        from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("x-api-key") == "env-secret-value"
            return _messages_response([_text_block("ok")])

        backend = ZCodeGlmBackend(
            base_url="http://mock.local/anthropic",
            api_key="env-secret-value",
            transport=httpx.MockTransport(handler),
        )
        request, context = _request()
        result = await backend.infer(request, context)
        serialized = json.dumps(result.wire_request)
        assert "env-secret-value" not in serialized
        await backend.close()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_system_only_request_gets_user_message() -> None:
    """Navigation opening calls are system-only; the wire still needs a user turn."""
    from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return _messages_response(
            [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "board_observe",
                    "input": {"node_id": "root"},
                }
            ],
            stop="tool_use",
        )

    backend = ZCodeGlmBackend(
        base_url="http://mock.local/anthropic",
        transport=httpx.MockTransport(handler),
    )
    model = ModelRef(
        backend="provider.zcode_glm", provider="zcode-coding-plan", model="GLM-5.3-Flash"
    )
    request = ModelRequest(
        model=model,
        messages=(Message(role=MessageRole.SYSTEM, parts=(TextPart(text="navigate"),)),),
    )
    result = await backend.infer(request, CallContext(run_id="run_test"))
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["system"] == "navigate"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    assert result.response.stop_reason.canonical == "tool_calls"
    await backend.close()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_assistant_first_history_gets_user_opener() -> None:
    """Tool-loop continuations start at assistant tool_use; wire must open with user."""
    from zgw_provider_zcode_glm.adapter import ZCodeGlmBackend
    from zugzwang_core.ports.model import ToolCallPart, ToolResultPart

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return _messages_response([_text_block("ok")])

    backend = ZCodeGlmBackend(
        base_url="http://mock.local/anthropic",
        transport=httpx.MockTransport(handler),
    )
    model = ModelRef(
        backend="provider.zcode_glm", provider="zcode-coding-plan", model="GLM-5.3-Flash"
    )
    request = ModelRequest(
        model=model,
        messages=(
            Message(
                role=MessageRole.ASSISTANT,
                parts=(
                    ToolCallPart(
                        tool_call_id="call_1", tool_name="board_observe", arguments={}
                    ),
                ),
            ),
            Message(
                role=MessageRole.TOOL,
                parts=(
                    ToolResultPart(
                        tool_call_id="call_1", tool_name="board_observe", content="fen"
                    ),
                ),
            ),
        ),
    )
    await backend.infer(request, CallContext(run_id="run_test"))
    body = captured["body"]
    assert isinstance(body, dict)
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant", "user"]
    await backend.close()
