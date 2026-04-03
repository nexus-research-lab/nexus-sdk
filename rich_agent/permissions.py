from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional


@dataclass
class BudgetConfig:
    usd: Optional[float] = None
    tokens: Optional[int] = None
    duration: Optional[timedelta] = None


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0


@dataclass
class PermissionScope:
    tools: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)


@dataclass
class Role:
    tools: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    max_budget: Optional[BudgetConfig] = None
    require_approval_for: List[str] = field(default_factory=list)
    bypass_guardrails: bool = False


@dataclass
class Policy:
    kind: str
    config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def rate_limit(cls, max_requests: int, window: str) -> "Policy":
        return cls(kind="rate_limit", config={"max_requests": max_requests, "window": window})

    @classmethod
    def token_limit(cls, max_tokens: int, window: str) -> "Policy":
        return cls(kind="token_limit", config={"max_tokens": max_tokens, "window": window})

    @classmethod
    def ip_allowlist(cls, cidrs: List[str]) -> "Policy":
        return cls(kind="ip_allowlist", config={"cidrs": list(cidrs)})


@dataclass
class PermissionConfig:
    roles: Dict[str, Role] = field(default_factory=dict)
    policies: List[Policy] = field(default_factory=list)
