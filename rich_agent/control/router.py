from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Router:
    name: str
    agents: Dict[str, Any]
    strategy: str = "llm"
    fallback: Optional[Any] = None

    def select(self, user_input: Any) -> Any:
        text = str(user_input).lower()
        for key, agent in self.agents.items():
            if key.lower() in text:
                return agent
        if self.fallback is not None:
            return self.fallback
        return next(iter(self.agents.values()))
