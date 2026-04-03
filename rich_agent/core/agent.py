from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from ..config.permissions import BudgetConfig, PermissionScope, RetryPolicy


InstructionsType = Union[str, Callable[[Any], str]]


@dataclass
class Agent:
    name: str
    instructions: InstructionsType
    model: Union[str, Any] = "echo"
    tools: List[Any] = field(default_factory=list)
    handoffs: List[Any] = field(default_factory=list)
    guardrails: Optional[Any] = None
    output_type: Optional[type] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    max_turns: Optional[int] = None
    max_budget: Optional[BudgetConfig] = None
    timeout: Optional[timedelta] = None
    retry_policy: Optional[RetryPolicy] = None
    permission_scope: Optional[PermissionScope] = None

    def resolve_instructions(self, context: Optional[Any] = None) -> str:
        if callable(self.instructions):
            return str(self.instructions(context))
        return str(self.instructions)

    def as_tool(self, name: Optional[str] = None, description: Optional[str] = None):
        from .runner import Runner
        from ..control.tool import ToolSpec

        async def invoke_subagent(input: Any = None, **kwargs: Any) -> Any:
            child_input = input if input is not None else kwargs
            result = await Runner.run(self, child_input)
            return result.final_output

        return ToolSpec.from_callable(
            invoke_subagent,
            name=name or self.name,
            description=description or ("Invoke the %s agent." % self.name),
        )
