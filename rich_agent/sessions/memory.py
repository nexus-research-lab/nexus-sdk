from dataclasses import dataclass, field
from typing import List, Optional

from ..result import MessageItem
from .base import Session


@dataclass
class InMemorySession(Session):
    session_id: Optional[str] = None
    messages: List[MessageItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        Session.__init__(self, session_id=self.session_id)

    async def get_history(self, limit: int = 50) -> List[MessageItem]:
        if limit <= 0:
            return []
        return list(self.messages[-limit:])

    async def add_messages(self, messages: List[MessageItem]) -> None:
        self.messages.extend(messages)

    async def clear(self) -> None:
        self.messages.clear()

    async def close(self) -> None:
        return None
