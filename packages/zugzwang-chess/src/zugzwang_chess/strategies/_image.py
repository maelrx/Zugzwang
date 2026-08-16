"""Shared image-part construction for chess strategies.

Strategies convert ``observation["image"]`` into a typed ImagePart. When the
runtime provides an artifact store, the PNG bytes are persisted as an
immutable CAS artifact and the part references it; otherwise the part still
carries the base64 payload and content hash.

No silent image-to-text fallback: strategies must require the
MULTIMODAL_IMAGE capability whenever they emit an ImagePart.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.model import Capability, ImagePart

IMAGE_REQUIRED_CAPABILITIES = frozenset({Capability.MULTIMODAL_IMAGE})


def image_part_from_observation(
    observation: dict[str, JsonValue],
    *,
    artifact_store: Any = None,
) -> ImagePart | None:
    """Build an ImagePart from observation['image'], storing bytes in CAS if possible."""
    image = observation.get("image")
    if not isinstance(image, dict):
        return None
    data_base64 = cast(str, image.get("data_base64"))
    if not data_base64:
        return None
    renderer = image.get("renderer")
    renderer_dict = cast(dict[str, JsonValue], renderer) if isinstance(renderer, dict) else {}
    content_sha256 = str(image.get("content_sha256", ""))
    artifact_ref: str | None = None
    if artifact_store is not None and content_sha256:
        import base64
        from types import SimpleNamespace

        try:
            payload = SimpleNamespace(
                media_type=str(image.get("mime", "image/png")),
                data=base64.b64decode(data_base64),
            )
            ref = artifact_store.put(payload)
            artifact_ref = ref.as_id() if hasattr(ref, "as_id") else str(ref)
        except Exception:
            artifact_ref = None
    mime_value = str(image.get("mime", "image/png"))
    mime = cast(
        Literal["image/png", "image/jpeg"],
        mime_value if mime_value in {"image/png", "image/jpeg"} else "image/png",
    )

    def _as_int(value: JsonValue, default: int) -> int:
        return int(value) if isinstance(value, (int, float)) else default

    return ImagePart(
        mime=mime,
        width=max(1, _as_int(image.get("width", 0), 1)),
        height=max(1, _as_int(image.get("height", 0), 1)),
        content_sha256=content_sha256 or "0" * 64,
        data_base64=data_base64,
        renderer=renderer_dict,
        artifact_ref=artifact_ref,
    )


def image_conflict_manifest(observation: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    """Return the explicit conflict manifest when image != symbolic state (FR-066)."""
    conflict = observation.get("image_conflict")
    if isinstance(conflict, dict):
        return cast(dict[str, JsonValue], conflict)
    return None


def build_message_parts(
    observation: dict[str, JsonValue],
    prompt_text: str,
    *,
    artifact_store: Any = None,
) -> tuple[tuple[Any, ...], frozenset[Capability]]:
    """Text part plus optional ImagePart, with the capabilities the parts demand."""
    from zugzwang_core.ports.model import TextPart

    parts: list[Any] = [TextPart(text=prompt_text)]
    image_part = image_part_from_observation(observation, artifact_store=artifact_store)
    required: frozenset[Capability] = frozenset()
    if image_part is not None:
        parts.append(image_part)
        required = IMAGE_REQUIRED_CAPABILITIES
    return tuple(parts), required
