"""Stable error taxonomy (design §26.4).

Errors carry a stable code, a category, retryability, a user message and
optional technical context. They are never reduced to generic strings.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    CONFIGURATION = "CONFIGURATION"
    CAPABILITY = "CAPABILITY"
    PROVIDER_TRANSPORT = "PROVIDER_TRANSPORT"
    PROVIDER_RESPONSE = "PROVIDER_RESPONSE"
    PARSING = "PARSING"
    ILLEGAL_ACTION = "ILLEGAL_ACTION"
    TOOL = "TOOL"
    ENVIRONMENT = "ENVIRONMENT"
    ENGINE = "ENGINE"
    BUDGET = "BUDGET"
    PERSISTENCE = "PERSISTENCE"
    ARTIFACT = "ARTIFACT"
    PLUGIN = "PLUGIN"
    SECURITY = "SECURITY"
    INTERNAL = "INTERNAL"


class Retryability(StrEnum):
    NONE = "none"
    TRANSPORT = "transport"
    THROTTLING = "throttling"
    TIMEOUT_UNKNOWN = "timeout_unknown"
    PARSE = "parse"
    LEGALITY = "legality"


class ZugzwangError(Exception):
    """Base class for all kernel errors.

    ``stable_code`` never changes for a given failure mode, so CLI exit codes
    and reports can rely on it.
    """

    category: ErrorCategory = ErrorCategory.INTERNAL
    stable_code: str = "ZGZ-INTERNAL-000"
    retryability: Retryability = Retryability.NONE

    def __init__(
        self,
        user_message: str,
        *,
        technical_context: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_context = technical_context
        self.cause = cause

    def secret_safe(self) -> str:
        """Human-safe rendering (secrets are redacted by the logging layer)."""
        return self.user_message

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "stable_code": self.stable_code,
            "retryability": self.retryability.value,
            "user_message": self.user_message,
            "technical_context": self.technical_context,
        }


class ConfigurationError(ZugzwangError):
    category = ErrorCategory.CONFIGURATION


class ManifestValidationError(ConfigurationError):
    stable_code = "ZGZ-CONFIGURATION-001"


class PatchApplicationError(ConfigurationError):
    stable_code = "ZGZ-CONFIGURATION-002"


class CapabilityError(ZugzwangError):
    category = ErrorCategory.CAPABILITY


class CapabilityMissingError(CapabilityError):
    stable_code = "ZGZ-CAPABILITY-001"


class ProviderTransportError(ZugzwangError):
    category = ErrorCategory.PROVIDER_TRANSPORT


class ProviderResponseError(ZugzwangError):
    category = ErrorCategory.PROVIDER_RESPONSE


class ProviderThrottlingError(ProviderTransportError):
    stable_code = "ZGZ-PROVIDER_TRANSPORT-001"
    retryability = Retryability.THROTTLING


class ProviderTimeoutError(ProviderTransportError):
    stable_code = "ZGZ-PROVIDER_TRANSPORT-002"
    retryability = Retryability.TIMEOUT_UNKNOWN


class ProviderConnectionError(ProviderTransportError):
    stable_code = "ZGZ-PROVIDER_TRANSPORT-003"
    retryability = Retryability.TRANSPORT


class ProviderServerError(ProviderResponseError):
    stable_code = "ZGZ-PROVIDER_RESPONSE-001"
    retryability = Retryability.TRANSPORT


class ParsingError(ZugzwangError):
    category = ErrorCategory.PARSING
    retryability = Retryability.PARSE


class OutputParseError(ParsingError):
    stable_code = "ZGZ-PARSING-001"


class IllegalActionError(ZugzwangError):
    category = ErrorCategory.ILLEGAL_ACTION
    retryability = Retryability.LEGALITY


class ToolError(ZugzwangError):
    category = ErrorCategory.TOOL


class ToolNotAllowedError(ToolError):
    stable_code = "ZGZ-TOOL-001"


class EnvironmentError_(ZugzwangError):
    category = ErrorCategory.ENVIRONMENT


class EngineError(ZugzwangError):
    category = ErrorCategory.ENGINE


class BudgetExceededError(ZugzwangError):
    category = ErrorCategory.BUDGET


class PersistenceError(ZugzwangError):
    category = ErrorCategory.PERSISTENCE


class ArtifactError(ZugzwangError):
    category = ErrorCategory.ARTIFACT


class PluginError(ZugzwangError):
    category = ErrorCategory.PLUGIN


class PluginApiMismatchError(PluginError):
    stable_code = "ZGZ-PLUGIN-001"


class SecurityError(ZugzwangError):
    category = ErrorCategory.SECURITY


class InternalError(ZugzwangError):
    category = ErrorCategory.INTERNAL


class StateTransitionError(InternalError):
    stable_code = "ZGZ-INTERNAL-001"


class InvariantError(InternalError):
    stable_code = "ZGZ-INTERNAL-002"
