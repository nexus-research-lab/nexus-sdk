import json
from dataclasses import dataclass, field
from typing import Any, List, Optional

from ..result import MessageItem
from .base import Session


@dataclass
class RedisSession(Session):
    url: str = ""
    session_id: Optional[str] = None
    key_prefix: str = "rich_agent:session"
    ttl_seconds: Optional[int] = None
    client: Any = None
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        Session.__init__(self, session_id=self.session_id)

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    @property
    def redis_key(self) -> str:
        return "%s:%s" % (self.key_prefix, self.session_id)

    async def get_history(self, limit: int = 50) -> List[MessageItem]:
        client = self._get_client()
        raw_items = await client.lrange(self.redis_key, -limit, -1)
        messages: List[MessageItem] = []
        for raw in raw_items:
            payload = json.loads(raw)
            messages.append(MessageItem(**payload))
        return messages

    async def add_messages(self, messages: List[MessageItem]) -> None:
        client = self._get_client()
        if not messages:
            return
        payloads = [
            json.dumps(
                {
                    "role": message.role,
                    "content": message.content,
                    "name": message.name,
                    "metadata": message.metadata,
                },
                ensure_ascii=False,
                default=str,
            )
            for message in messages
        ]
        await client.rpush(self.redis_key, *payloads)
        if self.ttl_seconds is not None:
            await client.expire(self.redis_key, self.ttl_seconds)

    async def clear(self) -> None:
        client = self._get_client()
        await client.delete(self.redis_key)

    async def close(self) -> None:
        client = self.client or self._client
        if client is None:
            return
        if hasattr(client, "aclose"):
            await client.aclose()
            return
        if hasattr(client, "close"):
            maybe_result = client.close()
            if hasattr(maybe_result, "__await__"):
                await maybe_result
