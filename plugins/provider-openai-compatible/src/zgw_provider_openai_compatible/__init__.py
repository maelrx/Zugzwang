"""OpenAI-compatible provider plugin entry point."""

from __future__ import annotations

from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

from .adapter import OpenAiCompatibleBackend

__version__ = "0.1.0.dev0"
__all__ = ["OpenAiCompatibleBackend", "plugin"]


class _Plugin:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="provider.openai_compatible",
            plugin_version=__version__,
            kind=PluginKind.PROVIDER,
            capabilities=(
                "text_input",
                "json_schema_output",
                "tool_calling",
                "usage_reporting",
                "seed",
            ),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


plugin = _Plugin()
