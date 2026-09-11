"""ZGW-0073: adapter lowering of image parts and capability preflight.

Offline contract tests: opencode FilePart data URL, openai-compatible
image_url content blocks, and the explicit failure when a backend without
MULTIMODAL_IMAGE receives an image request.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from zugzwang_core.domain.errors import CapabilityMissingError
from zugzwang_core.ports.model import (
    CallContext,
    Capability,
    ImagePart,
    Message,
    MessageRole,
    ModelRef,
    ModelRequest,
    TextPart,
)

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63600000020001002e8f6f890000000049454e44ae426082"
)

IMAGE_PART = ImagePart(
    mime="image/png",
    width=1,
    height=1,
    content_sha256=base64.b64encode(PNG_BYTES).decode() and "0" * 64,
    data_base64=base64.b64encode(PNG_BYTES).decode("ascii"),
    renderer={"renderer_id": "chess.board-png", "renderer_version": "0.1.0"},
)

MODEL = ModelRef(backend="provider.opencode", provider="opencode-go", model="mimo-v2.5")


def _request() -> ModelRequest:
    return ModelRequest(
        model=MODEL,
        messages=(Message(role=MessageRole.USER, parts=(TextPart(text="prompt"), IMAGE_PART)),),
        required_capabilities=frozenset({Capability.MULTIMODAL_IMAGE}),
    )


class TestOpenCodeImageLowering:
    @pytest.mark.asyncio
    async def test_image_becomes_file_part_with_data_url(self) -> None:
        from zgw_provider_opencode.adapter import OpenCodeBackend

        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            if request.method == "DELETE":
                return httpx.Response(200, json={"result": True})
            if request.content:
                captured["body"] = json.loads(request.content)
            if "/session/" in str(request.url) and str(request.url).endswith("/message"):
                return httpx.Response(
                    200,
                    json={
                        "info": {
                            "parentID": "msg_1",
                            "modelID": "mimo-v2.5",
                            "tokens": {"input": 12, "output": 3},
                        },
                        "parts": [{"type": "text", "text": "e2e4"}],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "ses_1",
                    "permission": [{"permission": "*", "pattern": "*", "action": "deny"}],
                },
            )

        backend = OpenCodeBackend(
            base_url="http://mock.local",
            provider_id="opencode-go",
            image_input=True,
            transport=httpx.MockTransport(handler),
        )
        result = await backend.infer(_request(), CallContext(run_id="run_1"))
        assert result.response.text() == "e2e4"
        body = captured["body"]
        assert isinstance(body, dict)
        parts = body["parts"]
        file_parts = [p for p in parts if p.get("type") == "file"]
        assert len(file_parts) == 1
        file_part = file_parts[0]
        assert file_part["mime"] == "image/png"
        assert file_part["url"].startswith("data:image/png;base64,")
        await backend.close()

    @pytest.mark.asyncio
    async def test_capability_declared_only_when_image_input(self) -> None:
        from zgw_provider_opencode.adapter import OpenCodeBackend

        plain = OpenCodeBackend(
            base_url="http://mock.local",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        vision = OpenCodeBackend(
            base_url="http://mock.local",
            image_input=True,
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        assert Capability.MULTIMODAL_IMAGE not in plain.descriptor.default_capabilities
        assert Capability.MULTIMODAL_IMAGE in vision.descriptor.default_capabilities
        await plain.close()
        await vision.close()


class TestOpenAiCompatibleImageLowering:
    @pytest.mark.asyncio
    async def test_image_becomes_image_url_content(self) -> None:
        from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "cmpl-1",
                    "model": "mimo-v2.5",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "e2e4"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )

        backend = OpenAiCompatibleBackend(
            base_url="http://mock.local/v1",
            image_input=True,
            transport=httpx.MockTransport(handler),
        )
        await backend.infer(_request(), CallContext(run_id="run_1"))
        body = captured["body"]
        assert isinstance(body, dict)
        messages = body["messages"]
        assert len(messages) == 1
        content = messages[0]["content"]
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "prompt"}
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        await backend.close()


class TestCapabilityPreflight:
    @pytest.mark.asyncio
    async def test_recording_backend_fails_explicitly_without_image(self) -> None:
        """No silent fallback: backend without MULTIMODAL_IMAGE must fail the call."""
        from zugzwang_runtime.execution.backend_caller import RecordingBackend
        from zugzwang_runtime.fakes.fake_backend import DeterministicModelBackend

        recorder = RecordingBackend(
            DeterministicModelBackend(),
            writer=object(),  # type: ignore[arg-type]
            event_sink=None,  # type: ignore[arg-type]
            artifact_store=None,
        )
        with pytest.raises(CapabilityMissingError):
            await recorder.infer(_request(), CallContext(run_id="run_1"))
