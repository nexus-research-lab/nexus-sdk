import json
from dataclasses import dataclass
from typing import Any, List

from ..result import MessageItem
from .base import Session


@dataclass
class EncryptedSession(Session):
    wrapped: Session
    secret_key: str

    def __post_init__(self) -> None:
        Session.__init__(self, session_id=self.wrapped.session_id)
        self._fernet = self._build_fernet(self.secret_key)

    @staticmethod
    def _build_fernet(secret_key: str):
        try:
            from cryptography.fernet import Fernet
        except ModuleNotFoundError as exc:
            raise RuntimeError("EncryptedSession requires the 'cryptography' package. Install nexus-sdk[sessions].") from exc

        return Fernet(secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key)

    @classmethod
    def generate_key(cls) -> str:
        try:
            from cryptography.fernet import Fernet
        except ModuleNotFoundError as exc:
            raise RuntimeError("EncryptedSession requires the 'cryptography' package. Install nexus-sdk[sessions].") from exc

        return Fernet.generate_key().decode("utf-8")

    def _encrypt_message(self, message: MessageItem) -> MessageItem:
        payload = json.dumps(message.content, ensure_ascii=False, default=str).encode("utf-8")
        encrypted = self._fernet.encrypt(payload).decode("utf-8")
        metadata = dict(message.metadata)
        metadata["encrypted"] = True
        return MessageItem(role=message.role, content=encrypted, name=message.name, metadata=metadata)

    def _decrypt_message(self, message: MessageItem) -> MessageItem:
        if not message.metadata.get("encrypted"):
            return message
        decrypted = self._fernet.decrypt(str(message.content).encode("utf-8")).decode("utf-8")
        metadata = dict(message.metadata)
        metadata.pop("encrypted", None)
        return MessageItem(
            role=message.role,
            content=json.loads(decrypted),
            name=message.name,
            metadata=metadata,
        )

    async def get_history(self, limit: int = 50) -> List[MessageItem]:
        messages = await self.wrapped.get_history(limit=limit)
        return [self._decrypt_message(message) for message in messages]

    async def add_messages(self, messages: List[MessageItem]) -> None:
        await self.wrapped.add_messages([self._encrypt_message(message) for message in messages])

    async def clear(self) -> None:
        await self.wrapped.clear()
