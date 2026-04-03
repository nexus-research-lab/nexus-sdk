from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class RunEvent:
    event_id: str
    type: str
    run_id: str
    agent_name: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)
