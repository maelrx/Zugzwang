"""Plugin registry: discovery, compatibility and lazy loading (design §19).

Plugins come from PyPA entry-point groups plus built-in first-party fakes.
Incompatible plugin_api versions are rejected, never adapted magically.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any, cast

from zugzwang_core.domain.errors import PluginApiMismatchError, PluginError
from zugzwang_core.domain.manifests import PluginSnapshot
from zugzwang_core.ports.plugin import (
    ALL_GROUPS,
    PluginDefinition,
    PluginDescriptor,
    PluginKind,
)

from ..fakes.registry_entries import (
    FAKE_BACKEND_ENTRY,
    FAKE_ENVIRONMENT_ENTRY,
    FAKE_EVALUATOR_ENTRY,
    FAKE_POLICY_ENTRY,
    FAKE_STRATEGY_ENTRY,
    FAKE_TASK_ENTRY,
)

_KIND_BY_GROUP: dict[str, PluginKind] = {
    "zugzwang.providers": PluginKind.PROVIDER,
    "zugzwang.environments": PluginKind.ENVIRONMENT,
    "zugzwang.tasks": PluginKind.TASK,
    "zugzwang.strategies": PluginKind.STRATEGY,
    "zugzwang.policies": PluginKind.POLICY,
    "zugzwang.verifiers": PluginKind.VERIFIER,
    "zugzwang.evaluators": PluginKind.EVALUATOR,
    "zugzwang.reporters": PluginKind.REPORTER,
    "zugzwang.codecs": PluginKind.CODEC,
}

_BUILTIN_DEFINITIONS: tuple[Any, ...] = (
    FAKE_BACKEND_ENTRY,
    FAKE_ENVIRONMENT_ENTRY,
    FAKE_EVALUATOR_ENTRY,
    FAKE_POLICY_ENTRY,
    FAKE_STRATEGY_ENTRY,
    FAKE_TASK_ENTRY,
)

_SUPPORTED_API_PREFIX = "zgw.plugin/"


def _load_entry_point(ep: importlib.metadata.EntryPoint, kind: PluginKind) -> PluginDefinition:
    try:
        obj = ep.load()
    except Exception as exc:
        raise PluginError(
            f"failed to load plugin entry point {ep.name}",
            technical_context=str(exc),
        ) from exc
    descriptor = cast(Any, getattr(obj, "descriptor", None))
    if descriptor is None or not isinstance(descriptor, PluginDescriptor):
        raise PluginError(
            f"entry point {ep.name} does not expose a valid PluginDescriptor",
            technical_context=f"<{type(cast(object, obj)).__name__}>",
        )
    if not descriptor.plugin_api.startswith(_SUPPORTED_API_PREFIX):
        raise PluginApiMismatchError(
            f"plugin {descriptor.plugin_id} declares unsupported plugin_api "
            f"{descriptor.plugin_api!r}",
            technical_context=f"entry point {ep.name}",
        )
    return obj


class PluginRegistry:
    """Lazy registry over built-ins and installed entry points."""

    def __init__(self, groups: tuple[str, ...] = ALL_GROUPS) -> None:
        self._groups = groups
        self._loaded: dict[str, PluginDefinition] = {}
        self._distributions: dict[str, str] = {}
        self._errors: list[str] = []
        self._load_builtins()
        self._discover()

    def _load_builtins(self) -> None:
        for definition in _BUILTIN_DEFINITIONS:
            self._loaded[definition.descriptor.plugin_id] = definition
            self._distributions[definition.descriptor.plugin_id] = "zugzwang-runtime"

    def _discover(self) -> None:
        eps = importlib.metadata.entry_points()
        for group in self._groups:
            if group not in eps.groups:
                continue
            kind = _KIND_BY_GROUP[group]
            for ep in eps.select(group=group):
                try:
                    definition = _load_entry_point(ep, kind)
                except PluginError as exc:
                    self._errors.append(str(exc.user_message))
                    continue
                plugin_id = definition.descriptor.plugin_id
                if plugin_id in self._loaded:
                    self._errors.append(f"duplicate plugin id {plugin_id!r} ignored")
                    continue
                self._loaded[plugin_id] = definition
                self._distributions[plugin_id] = ep.dist.name if ep.dist is not None else "unknown"

    def descriptors(self) -> tuple[PluginDescriptor, ...]:
        return tuple(
            sorted((d.descriptor for d in self._loaded.values()), key=lambda d: d.plugin_id)
        )

    def get(self, plugin_id: str) -> PluginDefinition:
        definition = self._loaded.get(plugin_id)
        if definition is None:
            raise PluginError(
                f"plugin {plugin_id!r} not found",
                technical_context=f"known={sorted(self._loaded)}",
            )
        return definition

    def descriptor(self, plugin_id: str) -> PluginDescriptor:
        return self.get(plugin_id).descriptor

    def get_kind(self, plugin_id: str, kind: PluginKind) -> Any:
        definition = self.get(plugin_id)
        descriptor = definition.descriptor
        if descriptor.kind is not kind:
            raise PluginError(f"plugin {plugin_id!r} is {descriptor.kind.value}, not {kind.value}")
        return definition

    def snapshot(self) -> tuple[PluginSnapshot, ...]:
        snapshots: list[PluginSnapshot] = []
        for descriptor in self.descriptors():
            distribution = self._distributions.get(descriptor.plugin_id)
            version = None
            if distribution is not None:
                try:
                    version = importlib.metadata.version(distribution)
                except importlib.metadata.PackageNotFoundError:
                    version = None
            snapshots.append(
                PluginSnapshot(
                    plugin_id=descriptor.plugin_id,
                    version=descriptor.plugin_version or version,
                    distribution=distribution,
                    api=descriptor.plugin_api,
                )
            )
        return tuple(snapshots)

    def errors(self) -> tuple[str, ...]:
        return tuple(self._errors)
