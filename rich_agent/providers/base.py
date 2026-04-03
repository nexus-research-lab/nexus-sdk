import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ModelToolCall:
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None


@dataclass
class ModelRequest:
    agent: Any
    instructions: str
    latest_input: Any
    history: List[Any] = field(default_factory=list)
    tool_results: List[Any] = field(default_factory=list)
    available_tools: List[Any] = field(default_factory=list)
    context: Any = None


@dataclass
class ModelResponse:
    message: Any = None
    tool_calls: List[ModelToolCall] = field(default_factory=list)
    handoff: Optional[str] = None
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_output: Any = None
    usage: Dict[str, int] = field(default_factory=dict)
    response_id: Optional[str] = None


class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...


@dataclass
class EchoModelProvider:
    model_name: str = "echo"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.tool_results:
            return ModelResponse(message=request.tool_results[-1].output, step_id="echo-tool-result")
        return ModelResponse(message=request.latest_input, step_id="echo-input")


@dataclass
class ModelConfig:
    name: Optional[str] = None
    provider: Optional[ModelProvider] = None
    settings: Dict[str, Any] = field(default_factory=dict)


def model_to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return [model_to_dict(item) for item in value]
    return value


def normalize_usage(value: Any) -> Dict[str, int]:
    usage = model_to_dict(value)
    if not isinstance(usage, dict):
        return {}
    normalized: Dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
        raw = usage.get(key, 0)
        if isinstance(raw, int):
            normalized[key] = raw
    return normalized


def serialize_tool_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def none_if_blank(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def resolve_request_model_name(request: Any) -> str:
    raw = getattr(getattr(request, "agent", None), "model", "")
    name = getattr(raw, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(raw)


def extract_openai_output_text(raw_output: Any) -> str:
    text_parts: List[str] = []
    if not isinstance(raw_output, list):
        return ""
    for item in raw_output:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for content_item in item.get("content", []) or []:
                if isinstance(content_item, dict) and content_item.get("type") in ("output_text", "text"):
                    text_parts.append(str(content_item.get("text", "")))
        elif item.get("type") in ("output_text", "text"):
            text_parts.append(str(item.get("text", "")))
    return "".join(text_parts)
