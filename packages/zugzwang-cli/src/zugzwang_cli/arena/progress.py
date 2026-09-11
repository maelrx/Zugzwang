"""Bounded, display-only projection of observable turn events (no chess logic)."""

from __future__ import annotations

import time
import uuid
from typing import Any


def new_progress(max_rounds: int, *, streaming: bool) -> dict[str, Any]:
    return {
        "turn_id": uuid.uuid4().hex,
        "started_at": time.time(),
        "finished_at": None,
        "status": "running",
        "phase": "preparing",
        "round": 0,
        "max_rounds": max_rounds,
        "streaming": streaming,
        "summaries": [],
        "steps": [],
    }


def project_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    kind = event.get("kind")
    state["round"] = event.get("round", state["round"])
    if kind == "summary":
        key = f"{state['round']}:{event.get('id', 'summary')}"
        row = {
            "id": key,
            "round": state["round"],
            "text": str(event["text"])[:12000],
            "source": event.get("source", "provider"),
        }
        summaries = state["summaries"]
        for index, old in enumerate(summaries):
            if old["id"] == key:
                summaries[index] = row
                break
        else:
            summaries.append(row)
        state["summaries"] = summaries[-32:]
    else:
        state["phase"] = str(kind)
        steps = state["steps"]
        row = {
            "kind": kind,
            "round": state["round"],
            "tool": event.get("tool"),
            "ok": event.get("ok"),
        }
        if not steps or steps[-1] != row:
            steps.append(row)
        state["steps"] = steps[-16:]
