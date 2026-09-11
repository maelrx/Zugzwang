"""Fail-closed Codex model-only launch profile, verified with the real CLI.

Native tools are unnecessary: the chess protocol is returned as text proposals.
Unknown flags/unsupported CLI versions fail instead of falling back to an agent.
"""

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
