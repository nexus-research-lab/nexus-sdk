from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional


@dataclass
class RunConfig:
    session: Optional[Any] = None
    harness: Optional[Any] = None
    model_override: Optional[str] = None
    permission_mode: str = "default"
    sandbox_mode: str = "workspace_write"
    stream_mode: str = "events"
    timeout: Optional[timedelta] = None
    max_turns: Optional[int] = None
    trace_metadata: Dict[str, Any] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)
