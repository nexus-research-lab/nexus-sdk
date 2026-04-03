import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import ModelRequest, ModelResponse, ModelToolCall, model_to_dict, normalize_usage, serialize_tool_output


@dataclass
class OpenAIProvider:
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    organization: Optional[str] = None
    project: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    client: Any = None
    _client: Any = field(default=None, init=False, repr=False)

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: Dict[str, Any] = {}
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            if self.base_url is not None:
                kwargs["base_url"] = self.base_url
            if self.organization is not None:
                kwargs["organization"] = self.organization
            if self.project is not None:
                kwargs["project"] = self.project
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            if self.max_retries is not None:
                kwargs["max_retries"] = self.max_retries
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _message_to_input_item(self, message: Any) -> List[Dict[str, Any]]:
        content = getattr(message, "content", None)
        metadata = dict(getattr(message, "metadata", {}) or {})
        role = getattr(message, "role", "")

        if role == "assistant" and metadata.get("provider") in ("openai", "azure") and metadata.get("raw_output"):
            raw_output = metadata["raw_output"]
            if isinstance(raw_output, list):
                return [model_to_dict(item) for item in raw_output]

        if role == "tool":
            tool_call_id = metadata.get("tool_call_id")
            if tool_call_id:
                return [
                    {
                        "type": "function_call_output",
                        "call_id": tool_call_id,
                        "output": serialize_tool_output(content),
                    }
                ]
            return [{"role": "user", "content": "Tool %s returned: %s" % (getattr(message, "name", "tool"), serialize_tool_output(content))}]

        if isinstance(content, list):
            return [{"role": role, "content": model_to_dict(content)}]
        return [{"role": role, "content": str(content)}]

    def _build_input(self, request: ModelRequest) -> List[Dict[str, Any]]:
        if request.history:
            built: List[Dict[str, Any]] = []
            for message in request.history:
                built.extend(self._message_to_input_item(message))
            return built
        if isinstance(request.latest_input, list):
            return list(request.latest_input)
        return [{"role": "user", "content": str(request.latest_input)}]

    def _build_tools(self, request: ModelRequest) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        for spec in request.available_tools:
            tools.append(
                {
                    "type": "function",
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.schema,
                    "strict": True,
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
            "instructions": request.instructions,
            "input": self._build_input(request),
        }
        tools = self._build_tools(request)
        if tools:
            params["tools"] = tools

        response = await client.responses.create(**params)
        raw_output = [model_to_dict(item) for item in getattr(response, "output", [])]
        tool_calls: List[ModelToolCall] = []
        for item in raw_output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            raw_arguments = item.get("arguments", {})
            if isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    arguments = {"raw_arguments": raw_arguments}
            else:
                arguments = raw_arguments
            tool_calls.append(
                ModelToolCall(
                    tool_name=str(item.get("name")),
                    arguments=arguments if isinstance(arguments, dict) else {"value": arguments},
                    call_id=item.get("call_id") or item.get("id"),
                )
            )

        return ModelResponse(
            message=getattr(response, "output_text", ""),
            tool_calls=tool_calls,
            step_id=getattr(response, "id", None),
            metadata={"provider": "openai"},
            raw_output=raw_output,
            usage=normalize_usage(getattr(response, "usage", {})),
            response_id=getattr(response, "id", None),
        )
