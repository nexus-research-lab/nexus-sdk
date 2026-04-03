import asyncio
import inspect
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union, get_args, get_origin

from ..core.errors import ToolExecutionError


@dataclass
class ToolPermission:
    require_approval: bool = False
    allowed_roles: List[str] = field(default_factory=list)
    audit_log: bool = False
    destructive: bool = False


@dataclass
class ToolContext:
    run_context: Any
    workspace: Any = None


def _unwrap_optional(annotation: Any) -> Tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def _json_schema_for_annotation(annotation: Any) -> Dict[str, Any]:
    annotation, optional = _unwrap_optional(annotation)
    origin = get_origin(annotation)

    if annotation in (str, inspect._empty):
        schema: Dict[str, Any] = {"type": "string"}
    elif annotation is int:
        schema = {"type": "integer"}
    elif annotation is float:
        schema = {"type": "number"}
    elif annotation is bool:
        schema = {"type": "boolean"}
    elif origin in (list, List):
        item_args = get_args(annotation)
        item_schema = _json_schema_for_annotation(item_args[0]) if item_args else {"type": "string"}
        schema = {"type": "array", "items": item_schema}
    elif origin in (dict, Dict):
        schema = {"type": "object"}
    else:
        schema = {"type": "string"}

    if optional:
        schema["nullable"] = True
    return schema


def infer_schema(fn: Callable[..., Any]) -> Dict[str, Any]:
    signature = inspect.signature(fn)
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, parameter in signature.parameters.items():
        if name == "context":
            continue
        properties[name] = _json_schema_for_annotation(parameter.annotation)
        if parameter.default is inspect._empty:
            required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


@dataclass
class ToolSpec:
    fn: Callable[..., Any]
    name: str
    description: str = ""
    schema: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[float] = None
    retries: int = 0
    permission: ToolPermission = field(default_factory=ToolPermission)

    @classmethod
    def from_callable(
        cls,
        fn: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        timeout: Optional[float] = None,
        retries: int = 0,
        permission: Optional[ToolPermission] = None,
    ) -> "ToolSpec":
        doc = inspect.getdoc(fn) or ""
        summary = doc.splitlines()[0] if doc else ""
        return cls(
            fn=fn,
            name=name or fn.__name__,
            description=description or summary,
            schema=infer_schema(fn),
            timeout=timeout,
            retries=retries,
            permission=permission or ToolPermission(),
        )

    async def invoke(self, arguments: Dict[str, Any], context: Optional[ToolContext] = None) -> Any:
        signature = inspect.signature(self.fn)
        call_args = dict(arguments)
        if "context" in signature.parameters and "context" not in call_args:
            call_args["context"] = context

        attempts = max(1, self.retries + 1)
        last_error: Optional[Exception] = None
        for _ in range(attempts):
            try:
                result = self.fn(**call_args)
                if self.timeout is not None:
                    return await asyncio.wait_for(_maybe_await(result), timeout=self.timeout)
                return await _maybe_await(result)
            except Exception as exc:
                last_error = exc
        raise ToolExecutionError(str(last_error)) from last_error


class ToolRegistry:
    def __init__(self, tools: Optional[Iterable[Any]] = None) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        for item in tools or []:
            self.register(item)

    def register(self, item: Any) -> ToolSpec:
        if isinstance(item, ToolSpec):
            tool_obj = item
        elif hasattr(item, "as_tool") and callable(item.as_tool):
            tool_obj = item.as_tool()
        elif callable(item):
            tool_obj = ToolSpec.from_callable(item)
        else:
            raise TypeError("Unsupported tool registration target.")
        self._tools[tool_obj.name] = tool_obj
        return tool_obj

    def register_many(self, tools: Iterable[Any]) -> None:
        for tool_obj in tools:
            self.register(tool_obj)

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def list(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def match(self, pattern: str) -> List[ToolSpec]:
        return [tool for tool in self._tools.values() if fnmatch(tool.name, pattern)]


def tool(
    fn: Optional[Callable[..., Any]] = None,
    *,
    description: Optional[str] = None,
    timeout: Optional[float] = None,
    retries: int = 0,
    permission: Optional[ToolPermission] = None,
):
    def decorator(func: Callable[..., Any]) -> ToolSpec:
        return ToolSpec.from_callable(
            func,
            description=description,
            timeout=timeout,
            retries=retries,
            permission=permission,
        )

    if fn is None:
        return decorator
    return decorator(fn)
