from __future__ import annotations

DIRECT_PROMPT_ID = "direct_v2_context"
AGENTIC_PROMPT_ID = "agentic_compat_v1"


def prompt_registry() -> dict[str, str]:
    return {
        "direct": DIRECT_PROMPT_ID,
        "agentic_compat": AGENTIC_PROMPT_ID,
    }
