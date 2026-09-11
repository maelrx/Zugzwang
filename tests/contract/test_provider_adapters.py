"""Provider adapter contract tests: both adapters pass the shared suite offline.

The OpenAI-compatible adapter runs against an httpx MockTransport; the
pydantic-ai adapter runs against a mock Model implementing the direct-request
protocol. No network, no secrets (ADR-031, M3 exit gate).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from .contract_suite import run_model_backend_contract


def _mock_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _chat_response(
    content: str, *, usage: dict | None = None, model: str = "test-model"
) -> httpx.Response:
    body = {
        "id": "cmpl-test",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return httpx.Response(200, json=body)


def _responses_response(content: str, *, model: str = "test-model") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "resp-test",
            "status": "completed",
            "model": model,
            "output": [
                {
                    "type": "reasoning",
                    "id": "rs-test",
                    "summary": [],
                },
                {
                    "type": "message",
                    "id": "msg-test",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": content, "annotations": []}],
                },
            ],
            "usage": {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19},
        },
    )


@pytest.mark.contract
@pytest.mark.asyncio
class TestOpenAiCompatibleAdapter:
    async def test_passes_model_contract(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/chat/completions")
            return _chat_response("e2e4")

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            api_key=None,
            transport=_mock_transport(handler),
        )
        await run_model_backend_contract(backend)
        await backend.close()

    async def test_usage_reported_as_provider_source(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        from zugzwang_core.domain.money import UsageSource
        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(lambda _: _chat_response("ok")),
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        assert result.response.usage.source is UsageSource.PROVIDER
        assert result.response.model_reported == "test-model"
        assert result.response.wire_fidelity.value == "full"
        await backend.close()

    async def test_429_is_throttling(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        from zugzwang_core.domain.errors import ProviderThrottlingError
        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(
                lambda _: httpx.Response(429, json={"error": {"message": "slow down"}})
            ),
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        with pytest.raises(ProviderThrottlingError):
            await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()

    async def test_500_is_server_error(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        from zugzwang_core.domain.errors import ProviderServerError
        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(lambda _: httpx.Response(503, json={})),
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        with pytest.raises(ProviderServerError):
            await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()

    async def test_tool_calls_normalized(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        body = {
            "id": "cmpl-tool",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "lookup",
                                    "arguments": '{"square": "e4"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(lambda _: httpx.Response(200, json=body)),
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        assert result.response.stop_reason.canonical == "tool_calls"
        assert result.response.tool_calls[0].tool_name == "lookup"
        assert result.response.tool_calls[0].arguments == {"square": "e4"}
        await backend.close()

    async def test_responses_profile_rewrites_harness_tool_calls_as_messages(self) -> None:
        # DeepSeek thinking-mode upstreams (Console Go) reject assistant
        # function_call items that have no originating reasoning; harness
        # preload calls are synthesized locally and must be lowered to text.
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
            ToolCallPart,
            ToolResultPart,
        )

        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return _responses_response("e2e4")

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(handler),
            profile="openai-responses",
            reasoning_effort="low",
        )
        request = ModelRequest(
            model=ModelRef(
                backend="provider.openai_compatible",
                provider="opencode-router",
                model="deepseek-v4.1-flash",
            ),
            messages=(
                Message(role=MessageRole.SYSTEM, parts=(TextPart(text="sys"),)),
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=(
                        ToolCallPart(
                            tool_call_id="harness:preload-root",
                            tool_name="board_observe",
                            arguments={"node_id": "n0"},
                        ),
                    ),
                ),
                Message(
                    role=MessageRole.TOOL,
                    parts=(
                        ToolResultPart(
                            tool_call_id="harness:preload-root",
                            tool_name="board_observe",
                            content='{"fen":"startpos"}',
                        ),
                    ),
                ),
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=(
                        ToolCallPart(
                            tool_call_id="call_abc",
                            tool_name="board_expand",
                            arguments={"node_id": "n0"},
                        ),
                    ),
                ),
                Message(
                    role=MessageRole.TOOL,
                    parts=(
                        ToolResultPart(
                            tool_call_id="call_abc",
                            tool_name="board_expand",
                            content='{"ok":true}',
                        ),
                    ),
                ),
            ),
        )
        await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()

        items = captured["input"]
        call_ids = [
            item.get("call_id")
            for item in items
            if item.get("type")
            in {
                "function_call",
                "function_call_output",
            }
        ]
        assert "harness:preload-root" not in call_ids
        assert "call_abc" in call_ids
        flattened = json.dumps(items)
        assert "[harness tool call]" in flattened
        assert "[harness tool result]" in flattened

    async def test_responses_profile_lowers_and_normalizes_nested_message(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        from zugzwang_core.domain.money import UsageSource
        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/responses")
            payload = json.loads(request.content)
            assert payload["model"] == "muse-spark-1.3-contributor-free"
            assert payload["input"][0]["content"][0]["type"] == "output_text"
            assert payload["input"][1]["content"][0]["type"] == "input_text"
            # ZGW-0101 commit 7060200: reasoning summaries are requested by default
            assert payload["reasoning"] == {"effort": "low", "summary": "auto"}
            assert payload["max_output_tokens"] == 1024
            assert "chess.strategy" not in payload
            assert payload["top_p"] == 0.1
            return _responses_response("e2e4")

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(handler),
            profile="openai-responses",
            reasoning_effort="low",
            default_max_output_tokens=1024,
        )
        request = ModelRequest(
            model=ModelRef(
                backend="provider.openai_compatible",
                provider="opencode-router",
                model="muse-spark-1.3-contributor-free",
            ),
            messages=(
                Message(role=MessageRole.ASSISTANT, parts=(TextPart(text="analysis"),)),
                Message(role=MessageRole.USER, parts=(TextPart(text="choose"),)),
            ),
            extensions={
                "chess.strategy": "direct",
                "provider.openai_compatible.top_p": 0.1,
            },
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        assert result.response.text() == "e2e4"
        assert result.response.request_id == "resp-test"
        assert result.response.usage.source is UsageSource.PROVIDER
        assert result.response.stop_reason.canonical == "end_turn"
        assert result.wire_request is not None
        assert result.wire_response is not None
        assert result.reasoning_telemetry is not None
        assert result.reasoning_telemetry.availability.reasoning_items
        await backend.close()


class _MockPaiModel:
    """Implements the pydantic_ai direct-request protocol surface."""

    model_name = "mock-pai-model"

    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self._calls = 0
        self.received_messages: list = []

    async def request(self, messages: list, model_request_parameters):
        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_ai.usage import RequestUsage

        self.received_messages.append(messages)
        reply = self._replies[min(self._calls, len(self._replies) - 1)]
        self._calls += 1
        response = ModelResponse(parts=[TextPart(content=reply)])
        usage = RequestUsage(
            input_tokens=10,
            cache_write_tokens=0,
            cache_read_tokens=0,
            output_tokens=3,
            input_audio_tokens=None,
            cache_audio_read_tokens=None,
            output_audio_tokens=None,
            details=None,
            cost=None,
        )
        return response, usage


@pytest.mark.contract
@pytest.mark.asyncio
class TestPydanticAiAdapter:
    async def test_passes_model_contract(self) -> None:
        from zgw_provider_pydantic_ai.adapter import PydanticAiBackend

        backend = PydanticAiBackend(_MockPaiModel(["g1f3"]))
        await run_model_backend_contract(backend)

    async def test_maps_system_and_user_messages(self) -> None:
        from pydantic_ai.messages import SystemPromptPart, UserPromptPart
        from zgw_provider_pydantic_ai.adapter import PydanticAiBackend

        from zugzwang_core.ports.model import (
            CallContext,
            Message,
            MessageRole,
            ModelRef,
            ModelRequest,
            TextPart,
        )

        mock = _MockPaiModel(["e2e4"])
        backend = PydanticAiBackend(mock)
        request = ModelRequest(
            model=ModelRef(backend="provider.pydantic_ai_direct", provider="mock", model="m"),
            messages=(
                Message(role=MessageRole.SYSTEM, parts=(TextPart(text="You play chess."),)),
                Message(role=MessageRole.USER, parts=(TextPart(text="Your move."),)),
            ),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        sent = mock.received_messages[0]
        assert isinstance(sent[0].parts[0], SystemPromptPart)
        assert isinstance(sent[1].parts[0], UserPromptPart)
        assert result.response.text() == "e2e4"
        assert result.response.usage.source.value == "provider"
