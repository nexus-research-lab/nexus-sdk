from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class AuditRecord:
    action: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLogger:
    records: List[AuditRecord] = field(default_factory=list)

    def log(self, action: str, payload: Dict[str, Any]) -> None:
        self.records.append(AuditRecord(action=action, timestamp=datetime.utcnow(), payload=payload))
