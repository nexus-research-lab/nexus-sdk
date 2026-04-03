from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict, Dict, List
from collections import defaultdict
import inspect


@dataclass
class HookContext:
    event_name: str
    payload: Dict[str, Any] = field(default_factory=dict)


class HookManager:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Callable[[HookContext], Any]]] = defaultdict(list)

    def register(self, event_name: str, handler: Callable[[HookContext], Any]) -> None:
        self._handlers[event_name].append(handler)

    async def dispatch(self, event_name: str, payload: Dict[str, Any]) -> None:
        context = HookContext(event_name=event_name, payload=payload)
        for handler in self._handlers.get(event_name, []):
            result = handler(context)
            if inspect.isawaitable(result):
                await result
