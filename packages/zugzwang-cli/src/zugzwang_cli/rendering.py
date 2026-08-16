"""CLI rendering: human (Rich, TTY-only colors), JSON and JSONL."""

from __future__ import annotations

import json
import sys
from typing import Any, cast

from pydantic import BaseModel


def render(value: Any, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(_to_json(value), indent=2, ensure_ascii=False, default=str)
    return render_human(value)


def _to_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return json.loads(value.model_dump_json())
    if isinstance(value, dict):
        raw: dict[Any, Any] = cast(dict[Any, Any], value)
        return {str(key): _to_json(raw[key]) for key in raw}
    if isinstance(value, (list, tuple)):
        raw_list: list[Any] = list(cast(list[Any], value))
        return [_to_json(v) for v in raw_list]
    return value


def render_human(value: Any) -> str:
    if isinstance(value, BaseModel):
        return _human_model(value)
    if isinstance(value, (list, tuple)):
        raw_list: list[Any] = list(cast(list[Any], value))
        return "\n".join(render_human(item) for item in raw_list)
    if isinstance(value, dict):
        raw: dict[Any, Any] = cast(dict[Any, Any], value)
        return "\n".join(f"{key}: {_human_scalar(raw[key])}" for key in raw)
    return str(value)


def _human_scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        raw_list: list[Any] = list(cast(list[Any], value))
        return ", ".join(str(v) for v in raw_list)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _human_model(model: BaseModel) -> str:
    data = model.model_dump()
    lines: list[str] = []
    for key, value in data.items():
        lines.append(f"{key}: {_human_scalar(value)}")
    return "\n".join(lines)


def print_result(value: Any, output_format: str) -> None:
    sys.stdout.write(render(value, output_format) + "\n")
