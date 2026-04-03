from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class KnowledgeDocument:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeSource(Protocol):
    async def search(self, query: str, top_k: int = 5) -> List[KnowledgeDocument]:
        ...
