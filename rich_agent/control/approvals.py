from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Protocol


@dataclass
class ApprovalRequest:
    request_id: str
    run_id: str
    tool_name: str
    tool_args: Dict[str, Any]
    reason: str
    risk_level: str
    editable: bool = True
    expires_at: Optional[datetime] = None


@dataclass
class ApprovalDecision:
    action: str
    updated_args: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None


class ApprovalHandler(Protocol):
    async def request(self, approval: ApprovalRequest) -> ApprovalDecision:
        ...


@dataclass
class InlineApprovalHandler:
    decision: ApprovalDecision = field(default_factory=lambda: ApprovalDecision(action="allow"))

    async def request(self, approval: ApprovalRequest) -> ApprovalDecision:
        return self.decision
