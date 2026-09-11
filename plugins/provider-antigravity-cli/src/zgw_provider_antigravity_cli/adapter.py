"""Antigravity CLI provider adapter.

Inference is unavailable until this CLI provides verifiable tools-off isolation.
The adapter retains its configuration identity for historical manifests.
"""

from __future__ import annotations

import os
import shutil

from zugzwang_core.domain.errors import (
    CapabilityMissingError,
)
from zugzwang_core.domain.provider_isolation import ProviderIsolationError
from zugzwang_core.ports.model import (
    BackendDescriptor,
    CallContext,
    Capability,
    CapabilityReport,
    ModelRef,
    ModelRequest,
    OnUnsupported,
    ProviderResult,
)


class AntigravityCliBackend:
    """Backend delegating inference to `agy --print` using the active session."""

    backend_id = "provider.antigravity_cli"
    backend_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        model: str = "gemini-3.8-flash-low",
        executable: str | None = None,
        timeout_seconds: float = 120.0,
        reasoning_effort: str | None = None,
    ) -> None:
        self._model = model
        self._executable = executable or os.environ.get(
            "ANTIGRAVITY_AGENTAPI_EXE",
            shutil.which("agy") or "/home/maelrx/.local/bin/agy",
        )
        self._timeout_seconds = timeout_seconds
        self._reasoning_effort = reasoning_effort

    @property
    def descriptor(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            plugin_api=self.plugin_api,
            default_capabilities=frozenset(
                {
                    Capability.TEXT_INPUT,
                    Capability.JSON_SCHEMA_OUTPUT,
                    Capability.TOOL_CALLING,
                    Capability.USAGE_REPORTING,
                }
            ),
            known_models=(),
            limitations=(
                "Antigravity CLI (agy) local execution",
                "uses logged-in Google Antigravity session (no API key)",
            ),
        )

    async def inspect_capabilities(
        self,
        model: ModelRef,
        required: frozenset[Capability] = frozenset(),
        preferred: frozenset[Capability] = frozenset(),
        on_unsupported: OnUnsupported = OnUnsupported.FAIL,
    ) -> CapabilityReport:
        supported = self.descriptor.default_capabilities
        missing = frozenset(c for c in required if c not in supported)
        if missing and on_unsupported is OnUnsupported.FAIL:
            raise CapabilityMissingError(
                f"Antigravity CLI backend lacks required capabilities: {sorted(c.value for c in missing)}",
                technical_context=f"required={sorted(c.value for c in required)}",
            )
        return CapabilityReport(
            model=model,
            supported=supported,
            missing_required=missing,
            missing_preferred=frozenset(c for c in preferred if c not in supported),
        )

    async def infer(self, request: ModelRequest, context: CallContext) -> ProviderResult:
        raise ProviderIsolationError(
            "Antigravity CLI blocked: this executable has no verified tools-off mode. "
            "Use a direct model-only provider; no fallback was attempted."
        )

    async def close(self) -> None:
        """No persistent daemon connection to close."""
        pass
