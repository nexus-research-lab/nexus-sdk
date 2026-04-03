from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import ModelRequest, ModelResponse, ModelToolCall, model_to_dict, normalize_usage, serialize_tool_output


@dataclass
class AnthropicProvider:
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    max_tokens: int = 1024
    client: Any = None
    _client: Any = field(default=None, init=False, repr=False)

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client
        if self._client is None:
            from anthropic import AsyncAnthropic

            kwargs: Dict[str, Any] = {}
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            if self.base_url is not None:
                kwargs["base_url"] = self.base_url
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            if self.max_retries is not None:
                kwargs["max_retries"] = self.max_retries
            self._client = AsyncAnthropic(**kwargs)
        return self._client

    def _message_to_api_message(self, message: Any) -> Dict[str, Any]:
        role = getattr(message, "role", "")
        content = getattr(message, "content", "")
        metadata = dict(getattr(message, "metadata", {}) or {})

        if role == "assistant" and metadata.get("provider") == "anthropic" and metadata.get("raw_output"):
            return {"role": "assistant", "content": model_to_dict(metadata["raw_output"])}

        if role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": metadata.get("tool_call_id"),
                        "content": serialize_tool_output(content),
                    }
                ],
            }

        if isinstance(content, list):
            return {"role": role, "content": model_to_dict(content)}
        return {"role": role, "content": str(content)}

    def _build_messages(self, request: ModelRequest) -> List[Dict[str, Any]]:
        if request.history:
            return [self._message_to_api_message(message) for message in request.history]
        return [{"role": "user", "content": str(request.latest_input)}]

    def _build_tools(self, request: ModelRequest) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        for spec in request.available_tools:
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "input_schema": spec.schema,
                }
            )
        return tools

    async def generate(self, request: ModelRequest) -> ModelResponse:
        client = self._get_client()
        model_name = str(getattr(request.agent, "model", ""))
        if "/" in model_name:
            model_name = model_name.split("/", 1)[1]
        params: Dict[str, Any] = {
            "model": model_name,
            "system": request.instructions,
            "messages": self._build_messages(request),
            "max_tokens": self.max_tokens,
        }
        tools = self._build_tools(request)
        if tools:
            params["tools"] = tools

        response = await client.messages.create(**params)
        raw_output = [model_to_dict(item) for item in getattr(response, "content", [])]
        text_parts: List[str] = []
        tool_calls: List[ModelToolCall] = []
        for item in raw_output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
            elif item.get("type") == "tool_use":
                tool_calls.append(
                    ModelToolCall(
                        tool_name=str(item.get("name")),
                        arguments=item.get("input", {}) if isinstance(item.get("input", {}), dict) else {"value": item.get("input")},
                        call_id=item.get("id"),
                    )
                )

        return ModelResponse(
            message="".join(text_parts),
            tool_calls=tool_calls,
            step_id=getattr(response, "id", None),
            metadata={"provider": "anthropic", "stop_reason": getattr(response, "stop_reason", None)},
            raw_output=raw_output,
            usage=normalize_usage(getattr(response, "usage", {})),
            response_id=getattr(response, "id", None),
        )
