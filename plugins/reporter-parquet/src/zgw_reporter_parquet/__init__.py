"""Parquet reporter plugin entry point."""

from __future__ import annotations

from zugzwang_core.ports.plugin import PluginDescriptor, PluginKind, TrustLevel

from .reporter import ParquetReporter

__version__ = "0.1.0.dev0"
__all__ = ["ParquetReporter", "plugin"]


class _Plugin:
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="reporter.parquet",
            plugin_version=__version__,
            kind=PluginKind.REPORTER,
            capabilities=("parquet", "duckdb"),
            license="GPL-3.0-or-later",
            trust=TrustLevel.FIRST_PARTY,
        )


plugin = _Plugin()
