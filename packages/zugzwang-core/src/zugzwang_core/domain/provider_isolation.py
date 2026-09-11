"""Provider-neutral prohibition of undeclared *executed* external tools.

Function-call proposals remain legal data for the kernel's own broker. Native
execution receipts are not proposals and may never be accepted as model-only.
"""

from __future__ import annotations

from typing import Any, cast

from .errors import SecurityError

ISOLATION_VERSION = "model-only/v1"
NATIVE_EXECUTION_TYPES = frozenset(
    {
        "command_execution",
        "mcp_tool_call",
        "web_search",
        "file_change",
        "web_search_call",
        "file_search_call",
        "code_interpreter_call",
        "computer_call",
        "shell_call",
        "local_shell_call",
        "mcp_call",
        "mcp_approval_request",
        "image_generation_call",
        "collab_agent_tool_call",
        "collab_agent_spawn_call",
        "tool",
        "server_tool_use",
        "web_search_tool_result",
        "code_execution_tool_result",
        # Codex CLI serializes some native activity as top-level events instead
        # of item.* envelopes; a covered envelope must not hide them.
        "exec_command_begin",
        "exec_command_end",
        "custom_tool_call",
        "dynamic_tool_call_request",
        "dynamic_tool_call_response",
        "hook_started",
        "hook_completed",
        "patch_apply_begin",
        "patch_apply_end",
        "unified_exec_startup",
        "unified_exec_interaction",
    }
)


class ProviderIsolationError(SecurityError):
    stable_code = "ZGZ-SECURITY-001"

    def __init__(self, message: str, *, wire_response: Any = None) -> None:
        super().__init__(message)
        self.wire_response = wire_response


def reject_native_execution(payload: Any) -> None:
    """Inspect typed wire envelopes, never keywords in reasoning/ordinary text."""
    pending: list[Any] = [payload]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            row = cast("dict[str, Any]", item)
            kind = row.get("type")
            if isinstance(kind, str) and kind in NATIVE_EXECUTION_TYPES:
                raise ProviderIsolationError(
                    f"Provider isolation violation: native execution {kind!r}; move rejected.",
                    wire_response=payload,
                )
            # Unknown executed item kinds fail closed in native envelopes.
            if kind in {"item.started", "item.updated", "item.completed"}:
                native = row.get("item")
                if isinstance(native, dict) and cast("dict[str, Any]", native).get("type") not in {
                    "agent_message",
                    "reasoning",
                    "raw_reasoning",
                    "error",
                    "todo_list",
                }:
                    raise ProviderIsolationError(
                        "Unrecognized native provider item; move rejected.", wire_response=payload
                    )
            if row.get("object") == "response" and isinstance(row.get("output"), list):
                for native in row["output"]:
                    if isinstance(native, dict) and cast("dict[str, Any]", native).get(
                        "type"
                    ) not in {
                        "message",
                        "reasoning",
                        "function_call",
                    }:
                        raise ProviderIsolationError(
                            "Unrecognized provider-side execution; move rejected.",
                            wire_response=payload,
                        )
            pending.extend(
                value
                for key, value in row.items()
                if key not in {"arguments", "parameters", "schema"}
            )
        elif isinstance(item, (list, tuple)):
            pending.extend(cast("list[Any]", item))
