"""Antigravity CLI provider plugin entry point."""

from __future__ import annotations

from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

from .adapter import AntigravityCliBackend

__version__ = "0.1.0.dev0"
__all__ = ["AntigravityCliBackend", "plugin"]


class _Plugin:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="provider.antigravity_cli",
            plugin_version=__version__,
            kind=PluginKind.PROVIDER,
            capabilities=(
                "text_input",
                "tool_calling",
                "reasoning_control",
                "usage_reporting",
            ),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


plugin = _Plugin()
