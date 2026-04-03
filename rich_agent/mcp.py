from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

from .tool import ToolRegistry


@dataclass
class MCPServer:
    transport: str
    endpoint: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    registry: ToolRegistry = field(default_factory=ToolRegistry)

    @classmethod
    def from_server(cls, url: str) -> "MCPServer":
        return cls(transport="server", endpoint=url)

    @classmethod
    def from_stdio(cls, command: str, args: Optional[List[str]] = None) -> "MCPServer":
        return cls(transport="stdio", command=command, args=args or [])

    @classmethod
    def from_tools(cls, name: str, tools: Iterable[Any]) -> "MCPServer":
        server = cls(transport="embedded", endpoint=name)
        server.registry.register_many(tools)
        return server
