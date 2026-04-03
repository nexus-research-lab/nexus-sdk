from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .todos import TodoItem


@dataclass
class MessageItem:
    role: str
    content: Any
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Artifact:
    kind: str
    path: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None
    output: Any = None
    duration_ms: Optional[float] = None
    approval: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class GuardrailRecord:
    phase: str
    action: str
    reason: Optional[str] = None


@dataclass
class UsageStep:
    step_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class UsageStats:
    steps: List[UsageStep] = field(default_factory=list)

    def record_step(self, step: UsageStep) -> None:
        if any(existing.step_id == step.step_id for existing in self.steps):
            return
        self.steps.append(step)

    @property
    def input_tokens(self) -> int:
        return sum(step.input_tokens for step in self.steps)

    @property
    def output_tokens(self) -> int:
        return sum(step.output_tokens for step in self.steps)

    @property
    def cache_read_tokens(self) -> int:
        return sum(step.cache_read_tokens for step in self.steps)

    @property
    def cache_write_tokens(self) -> int:
        return sum(step.cache_write_tokens for step in self.steps)


@dataclass
class CostBreakdown:
    total_usd: float = 0.0
    by_model: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_usage(cls, usage: UsageStats) -> "CostBreakdown":
        total = (usage.input_tokens * 0.000001) + (usage.output_tokens * 0.000002)
        return cls(total_usd=round(total, 6))


@dataclass
class RunResult:
    run_id: str
    final_output: Any
    messages: List[MessageItem]
    usage: UsageStats
    cost: CostBreakdown
    duration: timedelta
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    todos: List[TodoItem] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    guardrail_results: List[Any] = field(default_factory=list)
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    handoff_chain: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
