from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class GuardrailContext:
    run_id: str
    agent_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailResult:
    action: str = "allow"
    reason: Optional[str] = None
    rewritten_value: Any = None


@dataclass
class GuardrailSpec:
    kind: str
    fn: Callable[..., Any]
    tools: List[str] = field(default_factory=list)


@dataclass
class GuardrailConfig:
    input: List[GuardrailSpec] = field(default_factory=list)
    output: List[GuardrailSpec] = field(default_factory=list)
    tool: List[GuardrailSpec] = field(default_factory=list)


def InputGuardrail(fn: Callable[..., Any]) -> GuardrailSpec:
    return GuardrailSpec(kind="input", fn=fn)


def OutputGuardrail(fn: Callable[..., Any]) -> GuardrailSpec:
    return GuardrailSpec(kind="output", fn=fn)


def ToolGuardrail(tools: Optional[List[str]] = None):
    def decorator(fn: Callable[..., Any]) -> GuardrailSpec:
        return GuardrailSpec(kind="tool", fn=fn, tools=tools or [])

    return decorator
