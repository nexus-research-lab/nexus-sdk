import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..core.result import MessageItem
from .base import Session


@dataclass
class SQLiteSession(Session):
    path: str
    session_id: Optional[str] = None

    def __post_init__(self) -> None:
        Session.__init__(self, session_id=self.session_id)
        self._path = Path(self.path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT
                )
                """
            )

    async def get_history(self, limit: int = 50) -> List[MessageItem]:
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                """
                SELECT role, content, name
                FROM messages
                WHERE session_id = ?
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (self.session_id, limit),
            ).fetchall()
        rows.reverse()
        messages: List[MessageItem] = []
        for role, content, name in rows:
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                payload = content
            messages.append(MessageItem(role=role, content=payload, name=name))
        return messages

    async def add_messages(self, messages: List[MessageItem]) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.executemany(
                "INSERT INTO messages (session_id, role, content, name) VALUES (?, ?, ?, ?)",
                [
                    (
                        self.session_id,
                        message.role,
                        json.dumps(message.content, ensure_ascii=False),
                        message.name,
                    )
                    for message in messages
                ],
            )

    async def clear(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (self.session_id,))

    async def close(self) -> None:
        return None
