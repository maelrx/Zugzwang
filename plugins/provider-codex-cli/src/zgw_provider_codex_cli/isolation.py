"""Fail-closed Codex model-only launch profile, verified with the real CLI.

Native tools are unnecessary: the chess protocol is returned as text proposals.
Unknown flags/unsupported CLI versions fail instead of falling back to an agent.
"""

from __future__ import annotations

from typing import Any, cast

from zugzwang_core.domain.provider_isolation import ProviderIsolationError

# Top-level stream events this profile can vouch for. Everything else is a
# version-drift surface: reject instead of silently ignoring the unknown kind.
INERT_EVENT_TYPES = frozenset(
    {
        "thread.started",
        "turn.started",
        "turn.completed",
        "turn.failed",
        "item.started",
        "item.updated",
        "item.completed",
        "error",
    }
)


def reject_unknown_codex_event(event: Any) -> None:
    """Fail closed on top-level event kinds outside the verified surface."""
    if not isinstance(event, dict):
        return
    kind = cast("dict[str, Any]", event).get("type")
    if isinstance(kind, str) and kind not in INERT_EVENT_TYPES:
        raise ProviderIsolationError(
            f"Unrecognized codex stream event {kind!r}; inference rejected.",
            wire_response=event,
        )


DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "code_mode",
    "code_mode_host",
    "code_mode_only",
    "code_mode_prewarm",
    "apps",
    "plugins",
    "remote_plugin",
    "hooks",
    "multi_agent",
    "multi_agent_v2",
    "computer_use",
    "browser_use",
    "browser_use_external",
    "in_app_browser",
    "image_generation",
    "view_image",
    "workspace_dependencies",
    "skill_search",
    "skill_mcp_dependency_install",
    "goals",
    "enable_request_compression",
)


def model_only_args() -> list[str]:
    args = [
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "-c",
        'web_search="disabled"',
        "-c",
        "mcp_servers={}",
        "-c",
        'approval_policy="never"',
    ]
    for feature in DISABLED_FEATURES:
        args.extend(["--disable", feature])
    args.extend(["--enable", "skip_host_skill_discovery"])
    return args
