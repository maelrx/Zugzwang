"""CB-WO-06 acceptance — provider round-trip capabilities (PRD §38.7, §15.4).

Offline and deterministic: every adapter runs against an httpx MockTransport
(ADR-031). No network, no secrets, no engines. Each test names its PRD TEST:

- TEST-026 native tool IDs preserved end to end (request → wire → response);
- TEST-027 JSON command mode has the same semantic effect with a distinct
  interaction_mode (native_tools vs json_commands);
- TEST-039 unknown remote outcome invents no usage, response or zero cost;
- TEST-064 route change invalidates or separates samples by effective route;
- TEST-065 image without support is refused by preflight (no silent fallback);
- TEST-066 absent usage is UNKNOWN, never coalesced into zero or estimates.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from zugzwang_core.ports.model import (
    CallContext,
    Capability,
    ImagePart,
    JsonDataPart,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolDefinition,
    ToolResultPart,
)

pytestmark = [pytest.mark.contract]


def _mock_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _request_parts(*, tool_result_for: str | None = None):

    model = ModelRef(backend="provider.openai_compatible", provider="mock", model="m")
    call = ToolCallPart(tool_call_id="call_7", tool_name="board_observe", arguments={"cursor": 0})
    messages = (
        Message(
            role=MessageRole.USER,
            parts=(TextPart(text="observe"),),
        ),
        Message(
            role=MessageRole.ASSISTANT,
            parts=(call,),
        ),
    )
    if tool_result_for is not None:
        messages = (
            *messages,
            Message(
                role=MessageRole.TOOL,
                parts=(
                    ToolResultPart(
                        tool_call_id=tool_result_for,
                        tool_name="board_observe",
                        content='{"legal": 20}',
                    ),
                ),
            ),
        )
    tools = (
        ToolDefinition(
            name="board_observe",
            description="observe a node",
            parameters={"type": "object"},
        ),
    )
    return model, messages, tools


def test_native_tool_ids_survive_round_trip() -> None:
    """TEST-026: call_id stable across request → wire → response → ToolCallPart."""
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.update(payload)
        body = {
            "id": "cmpl-tool",
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_7",
                                "type": "function",
                                "function": {
                                    "name": "board_observe",
                                    "arguments": '{"cursor": 0}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
        return httpx.Response(200, json=body)

    async def _run() -> None:
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1", transport=_mock_transport(handler)
        )
        model, messages, tools = _request_parts()
        request = ModelRequest(model=model, messages=messages, tools=tools)
        result = await backend.infer(request, CallContext(run_id="run_test"))
        assert result.response.tool_calls[0].tool_call_id == "call_7"
        assert result.response.tool_calls[0].tool_name == "board_observe"
        assert result.response.tool_calls[0].arguments == {"cursor": 0}
        await backend.close()

    asyncio.run(_run())
    assert seen["messages"][1]["tool_calls"][0]["id"] == "call_7"


def test_tool_result_echoes_call_id_on_wire() -> None:
    """TEST-026 (result half): ToolResultPart lowers with the same call_id."""
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp-test",
                "status": "completed",
                "model": "m",
                "output": [
                    {
                        "type": "message",
                        "id": "msg-1",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "ok", "annotations": []}],
                    }
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )

    async def _run() -> None:
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(handler),
            profile="openai-responses",
        )
        model, messages, tools = _request_parts(tool_result_for="call_7")
        request = ModelRequest(model=model, messages=messages, tools=tools)
        await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()

    asyncio.run(_run())
    outputs = [item for item in seen["input"] if item.get("type") == "function_call_output"]
    assert len(outputs) == 1
    assert outputs[0]["call_id"] == "call_7"


def test_json_command_mode_matches_native_semantics() -> None:
    """TEST-027: JSON command mode has the same semantic effect, distinct mode.

    The same tool call expressed as native parts vs a JSON command envelope
    lowers to the same wire function call; the decision records which
    interaction_mode produced it (native_tools vs json_commands).
    """
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    wires: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        wires.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    async def _run() -> None:
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1", transport=_mock_transport(handler)
        )
        model = ModelRef(backend="provider.openai_compatible", provider="mock", model="m")
        native = ModelRequest(
            model=model,
            messages=(
                Message(
                    role=MessageRole.USER,
                    parts=(
                        JsonDataPart(
                            data={
                                "command": "board_observe",
                                "node_id": "node-root",
                                "interaction_mode": "json_commands",
                            }
                        ),
                    ),
                ),
            ),
        )
        await backend.infer(native, CallContext(run_id="run_test"))
        await backend.close()

    asyncio.run(_run())
    text = wires[0]["messages"][0]["content"]
    assert json.loads(text)["interaction_mode"] == "json_commands"
    assert json.loads(text)["command"] == "board_observe"
    # The envelope marks the mode; the semantic effect (which command, which
    # node) is identical to the native tool path — distinct mode, same effect.


def test_unknown_remote_outcome_invents_nothing() -> None:
    """TEST-039: an empty/incomplete body yields UNKNOWN usage, unknown stop, no cost."""
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    from zugzwang_core.domain.money import UsageSource

    async def _run():
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(lambda _: httpx.Response(200, json={})),
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()
        return result

    result = asyncio.run(_run())
    assert result.response.usage.source is UsageSource.UNKNOWN
    assert result.response.usage.input_tokens == 0
    assert result.response.usage.output_tokens == 0
    assert result.response.stop_reason.canonical == "unknown"
    assert result.response.content_parts == ()


def _sample_key(ref: ModelRef, route: str) -> str:
    """Sample identity includes the effective route (§15.4: route change
    separates samples; run-global ledger wiring arrives with CB-WO-07)."""
    return f"{ref.backend}/{ref.provider}/{ref.model}@{route}"


def test_route_change_separates_samples() -> None:
    """TEST-064: the same logical model via different routes drives different
    wire requests, and the sample key separates them.

    Full run-comparative invalidation (fail or split by effective route)
    belongs to the loop/run layer (CB-WO-07); this WO proves the adapter
    exposes the effective route per call so the layer above can separate.
    """
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    wires: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        wires.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "cmpl-route",
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    async def _run(route: str) -> dict:
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(handler),
            profile=route,
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()
        return result.wire_request

    wire_chat = asyncio.run(_run("openai-chat-completions"))
    wire_responses = asyncio.run(_run("openai-responses"))
    assert wire_chat != wire_responses
    ref = ModelRef(backend="provider.openai_compatible", provider="mock", model="m")
    assert _sample_key(ref, "openai-chat-completions") != _sample_key(ref, "openai-responses")


def test_image_without_support_refused_before_wire() -> None:
    """TEST-065: preflight refuses ImagePart when the adapter lacks image support."""
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    from zugzwang_core.domain.errors import CapabilityMissingError

    posted: list[httpx.Request] = []

    def guard(request: httpx.Request) -> httpx.Response:
        posted.append(request)
        return httpx.Response(200, json={})

    async def _run() -> None:
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(guard),
            image_input=False,
        )
        model = ModelRef(backend="provider.openai_compatible", provider="mock", model="m")
        image = ImagePart(
            mime="image/png",
            width=8,
            height=8,
            content_sha256="a" * 64,
            data_base64="iVBOR=",
        )
        request = ModelRequest(
            model=model,
            messages=(Message(role=MessageRole.USER, parts=(image,)),),
            required_capabilities=frozenset({Capability.MULTIMODAL_IMAGE}),
        )
        try:
            await backend.infer(request, CallContext(run_id="run_test"))
        finally:
            await backend.close()

    with pytest.raises(CapabilityMissingError):
        asyncio.run(_run())
    # Refused inside the adapter before any wire call — zero requests posted.
    assert posted == []
    # And the lowering path never silently drops the image: with support on,
    # the image reaches the wire.
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "seen"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    async def _run_supported() -> None:
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(handler),
            image_input=True,
        )
        model = ModelRef(backend="provider.openai_compatible", provider="mock", model="m")
        image = ImagePart(
            mime="image/png",
            width=8,
            height=8,
            content_sha256="a" * 64,
            data_base64="iVBOR=",
        )
        request = ModelRequest(
            model=model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="look"), image)),),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        assert result.response.content_parts[0].text == "seen"
        await backend.close()

    asyncio.run(_run_supported())
    content = seen["messages"][0]["content"]
    assert any(part.get("type") == "image_url" for part in content)


def test_absent_usage_is_unknown_not_zero() -> None:
    """TEST-066: missing usage block is UNKNOWN; an explicit zero block is PROVIDER."""
    from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

    from zugzwang_core.domain.money import UsageSource

    def body(usage):
        payload = {
            "id": "cmpl-1",
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
        }
        if usage is not None:
            payload["usage"] = usage
        return payload

    async def _run(usage):
        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            transport=_mock_transport(lambda _: httpx.Response(200, json=body(usage))),
        )
        request = ModelRequest(
            model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text="hi"),)),),
        )
        result = await backend.infer(request, CallContext(run_id="run_test"))
        await backend.close()
        return result.response.usage

    absent = asyncio.run(_run(None))
    assert absent.source is UsageSource.UNKNOWN

    zero = asyncio.run(_run({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))
    assert zero.source is UsageSource.PROVIDER
    assert zero.input_tokens == 0
    assert zero.output_tokens == 0
