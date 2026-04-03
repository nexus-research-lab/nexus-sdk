from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Subagent:
    name: str
    agent: Any
    context_policy: str = "summary_only"
    workspace_policy: str = "ephemeral"
    result_policy: str = "structured_output"
    parallelism: int = 1
    max_budget: Optional[Any] = None
