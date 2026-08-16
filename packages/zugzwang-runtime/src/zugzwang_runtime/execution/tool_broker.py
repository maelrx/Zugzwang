"""Typed tool broker with an explicit allowlist (design §13.5, §20).

Discovery never implies authorization: only tools named in the allowlist
dispatch; everything else raises ToolNotAllowedError and emits a security
event upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zugzwang_core.domain.errors import ToolNotAllowedError
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.tool import Tool, ToolContext, ToolResult


@dataclass(slots=True)
class ToolBroker:
    """Registry + allowlist for typed tools."""

    _tools: dict[str, Tool] = field(default_factory=lambda: {})
    _allowlist: set[str] = field(default_factory=lambda: set())

    def register(self, tool: Tool) -> None:
        name = tool.descriptor.name
        if name in self._tools:
            raise ToolNotAllowedError(f"tool {name!r} is already registered")
        self._tools[name] = tool

    def allow(self, name: str) -> None:
        if name not in self._tools:
            raise ToolNotAllowedError(f"tool {name!r} is not registered")
        self._allowlist.add(name)

    def definitions(self) -> list[dict[str, JsonValue]]:
        return [
            {
                "name": tool.descriptor.name,
                "description": tool.descriptor.description,
                "parameters": tool.descriptor.input_schema,
            }
            for tool in self._tools.values()
            if tool.descriptor.name in self._allowlist
        ]

    async def invoke(
        self, name: str, arguments: dict[str, JsonValue], context: ToolContext
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotAllowedError(f"tool {name!r} is not registered")
        if name not in self._allowlist:
            raise ToolNotAllowedError(
                f"tool {name!r} is not in the run allowlist",
                technical_context="discovery does not imply authorization",
            )
        return await tool.invoke(arguments, context)

    @property
    def allowlisted(self) -> tuple[str, ...]:
        return tuple(sorted(self._allowlist))
