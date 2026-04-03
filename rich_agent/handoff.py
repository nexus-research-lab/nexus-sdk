from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Handoff:
    target: Any
    condition: str
    input_filter: Optional[Callable[[Any], Any]] = None
    history_filter: Optional[Callable[[Any], Any]] = None
