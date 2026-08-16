"""Exit codes and output handling.

stdout carries the result; stderr carries diagnostics. Exit codes are stable
and documented (design §18.3).
"""

from __future__ import annotations

import sys
from enum import IntEnum

from zugzwang_core.domain.errors import (
    ArtifactError,
    BudgetExceededError,
    CapabilityError,
    ConfigurationError,
    ParsingError,
    PersistenceError,
    PluginError,
    ProviderResponseError,
    ProviderTransportError,
    ToolError,
    ZugzwangError,
)


class ExitCode(IntEnum):
    OK = 0
    INTERNAL = 1
    CONFIGURATION = 2
    CAPABILITY = 3
    BUDGET = 4
    PERSISTENCE = 5
    PLUGIN = 6
    PROVIDER = 7
    INTERRUPTED = 130


def exit_code_for(exc: BaseException) -> ExitCode:
    if isinstance(exc, KeyboardInterrupt):
        return ExitCode.INTERRUPTED
    if isinstance(exc, ConfigurationError):
        return ExitCode.CONFIGURATION
    if isinstance(exc, CapabilityError):
        return ExitCode.CAPABILITY
    if isinstance(exc, BudgetExceededError):
        return ExitCode.BUDGET
    if isinstance(exc, (PersistenceError, ArtifactError)):
        return ExitCode.PERSISTENCE
    if isinstance(exc, PluginError):
        return ExitCode.PLUGIN
    if isinstance(exc, (ProviderTransportError, ProviderResponseError)):
        return ExitCode.PROVIDER
    if isinstance(exc, (ParsingError, ToolError, ZugzwangError)):
        return ExitCode.INTERNAL
    return ExitCode.INTERNAL


def print_diagnostic(error: BaseException) -> None:
    if isinstance(error, ZugzwangError):
        sys.stderr.write(
            f"[{error.stable_code}] {error.user_message}"
            + (f" ({error.technical_context})" if error.technical_context else "")
            + "\n"
        )
    else:
        sys.stderr.write(f"[ZGZ-INTERNAL-000] {error}\n")
