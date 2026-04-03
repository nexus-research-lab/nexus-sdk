import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, List, Optional

from ..core.result import MessageItem
from .base import Session


@dataclass
class PostgresSession(Session):
    url: str = ""
    session_id: Optional[str] = None
    table_name: str = "rich_agent_messages"
    ttl_seconds: Optional[int] = None
    connection: Any = None
    _initialized: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        Session.__init__(self, session_id=self.session_id)

    async def _get_connection(self) -> Any:
        if self.connection is not None:
            return self.connection
        import psycopg

        self.connection = await psycopg.AsyncConnection.connect(self.url)
        return self.connection

    async def _ensure_table(self) -> Any:
        if self._initialized:
            return
        conn = await self._get_connection()
        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS %s (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content JSONB NOT NULL,
                    name TEXT,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NULL
                )
                """
                % self.table_name
            )
        await conn.commit()
        self._initialized = True

    async def get_history(self, limit: int = 50) -> List[MessageItem]:
        await self._ensure_table()
        conn = await self._get_connection()
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT role, content, name, metadata
                FROM %s
                WHERE session_id = %%s
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY id DESC
                LIMIT %%s
                """
                % self.table_name,
                (self.session_id, limit),
            )
            rows = await cur.fetchall()
        rows.reverse()
        return [
            MessageItem(role=role, content=content, name=name, metadata=metadata or {})
            for role, content, name, metadata in rows
        ]

    async def add_messages(self, messages: List[MessageItem]) -> None:
        await self._ensure_table()
        conn = await self._get_connection()
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT INTO %s (session_id, role, content, name, metadata, expires_at)
                VALUES (%%s, %%s, %%s::jsonb, %%s, %%s::jsonb, %%s)
                """
                % self.table_name,
                [
                    (
                        self.session_id,
                        message.role,
                        json.dumps(message.content, ensure_ascii=False, default=str),
                        message.name,
                        json.dumps(message.metadata, ensure_ascii=False, default=str),
                        None if self.ttl_seconds is None else datetime.utcnow() + timedelta(seconds=int(self.ttl_seconds)),
                    )
                    for message in messages
                ],
            )
        await conn.commit()

    async def clear(self) -> None:
        await self._ensure_table()
        conn = await self._get_connection()
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM %s WHERE session_id = %%s" % self.table_name, (self.session_id,))
        await conn.commit()

    async def close(self) -> None:
        if self.connection is None:
            return
        await self.connection.close()
        self.connection = None
        self._initialized = False
