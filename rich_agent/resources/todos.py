from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol


@dataclass
class TodoItem:
    title: str
    status: str = "pending"
    detail: Optional[str] = None
    owner: Optional[str] = None


class TodoStore(Protocol):
    async def list(self, session_id: str) -> List[TodoItem]:
        ...

    async def save(self, session_id: str, todos: List[TodoItem]) -> None:
        ...


@dataclass
class SessionTodoStore:
    _store: Dict[str, List[TodoItem]] = field(default_factory=dict)

    async def list(self, session_id: str) -> List[TodoItem]:
        return list(self._store.get(session_id, []))

    async def save(self, session_id: str, todos: List[TodoItem]) -> None:
        self._store[session_id] = list(todos)
