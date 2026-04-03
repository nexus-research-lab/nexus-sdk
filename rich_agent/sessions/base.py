from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import uuid4

from ..result import MessageItem


class Session(ABC):
    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or uuid4().hex

    @classmethod
    def from_redis(cls, url: str, session_id: Optional[str] = None):
        from .redis import RedisSession

        return RedisSession(url=url, session_id=session_id)

    @classmethod
    def from_postgres(cls, url: str, session_id: Optional[str] = None):
        from .postgres import PostgresSession

        return PostgresSession(url=url, session_id=session_id)

    @classmethod
    def from_sqlite(cls, path: str, session_id: Optional[str] = None):
        from .sqlite import SQLiteSession

        return SQLiteSession(path=path, session_id=session_id)

    @abstractmethod
    async def get_history(self, limit: int = 50) -> List[MessageItem]:
        raise NotImplementedError

    @abstractmethod
    async def add_messages(self, messages: List[MessageItem]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def clear(self) -> None:
        raise NotImplementedError
