"""Tool registry for the TOFAN agent runtime.

Tools are registered explicitly in application code. An agent may execute only
tools that are both registered here and enabled for that agent in the database.
"""

from dataclasses import dataclass
from typing import Callable


class ToolExecutionError(RuntimeError):
    """Raised when a registered tool cannot be executed."""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[[str], str]
    sensitive: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError("Unknown tool.")
        return tool

    def names(self) -> list[str]:
        return sorted(self._tools)


def echo_tool(input_text: str) -> str:
    return input_text


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="academy.health",
            description="Return a simple runtime health result.",
            handler=lambda _: "ok",
        )
    )
    registry.register(
        ToolDefinition(
            name="academy.echo",
            description="Development-only echo tool.",
            handler=echo_tool,
        )
    )
    return registry
