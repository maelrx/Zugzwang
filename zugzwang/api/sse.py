from __future__ import annotations

from typing import Any


def build_sse_event(event: str, data: Any) -> dict[str, Any]:
    """Small helper for SSE responses used in job log streaming."""
    return {"event": event, "data": data}

