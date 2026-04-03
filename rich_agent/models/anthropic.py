import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from .base import ModelRequest, ModelResponse, ModelToolCall, model_to_dict, none_if_blank, normalize_usage, resolve_request_model_name, serialize_tool_output


@dataclass
class AnthropicProvider:
    api_key: Optional[str] = None
    auth_token: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    max_tokens: int = 1024
    default_headers: Optional[Dict[str, str]] = None
    default_haiku_model: Optional[str] = None
    default_opus_model: Optional[str] = None
    default_sonnet_model: Optional[str] = None
    reasoning_model: Optional[str] = None
    use_compatible_http: Optional[bool] = None
    client: Any = None
    _client: Any = field(default=None, init=False, repr=False)
    _http_client: Any = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "AnthropicProvider":
        api_version = none_if_blank(os.getenv("ANTHROPIC_API_VERSION"))
        default_headers: Dict[str, str] = {}
        if api_version is not None:
            default_headers["anthropic-version"] = api_version
        return cls(
            api_key=none_if_blank(os.getenv("ANTHROPIC_API_KEY")),
            auth_token=none_if_blank(os.getenv("ANTHROPIC_AUTH_TOKEN")),
            base_url=none_if_blank(os.getenv("ANTHROPIC_BASE_URL")),
            api_version=api_version,
            default_headers=default_headers or None,
            default_haiku_model=none_if_blank(os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL")),
            default_opus_model=none_if_blank(os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL")),
            default_sonnet_model=none_if_blank(os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL")),
            reasoning_model=none_if_blank(os.getenv("ANTHROPIC_REASONING_MODEL")),
            use_compatible_http=(
                None
                if none_if_blank(os.getenv("ANTHROPIC_USE_COMPATIBLE_HTTP")) is None
                else none_if_blank(os.getenv("ANTHROPIC_USE_COMPATIBLE_HTTP", "")).lower() in {"1", "true", "yes", "on"}
            ),
        )

    def _should_use_compatible_http(self) -> bool:
        if self.use_compatible_http is not None:
            return self.use_compatible_http
        return False

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client
        if self._client is None:
            from anthropic import AsyncAnthropic

            kwargs: Dict[str, Any] = {}
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            if self.auth_token is not None:
                kwargs["auth_token"] = self.auth_token
            if self.base_url is not None:
                kwargs["base_url"] = self.base_url
            if self.default_headers is not None:
                kwargs["default_headers"] = self.default_headers
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            if self.max_retries is not None:
                kwargs["max_retries"] = self.max_retries
            self._client = AsyncAnthropic(**kwargs)
        return self._client

    async def close(self) -> None:
        for client in [self.client or self._client, self._http_client]:
            if client is None:
                continue
            if hasattr(client, "aclose"):
                await client.aclose()
                continue
            if hasattr(client, "close"):
                maybe_result = client.close()
                if hasattr(maybe_result, "__await__"):
                    await maybe_result

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

    def resolve_model_name(self, model_name: str) -> str:
        lowered = model_name.lower()
        if "claude" not in lowered:
            return model_name
        if "opus" in lowered and self.default_opus_model:
            return self.default_opus_model
        if "haiku" in lowered and self.default_haiku_model:
            return self.default_haiku_model
        if "sonnet" in lowered and self.default_sonnet_model:
            return self.default_sonnet_model
        if "reason" in lowered and self.reasoning_model:
            return self.reasoning_model
        return model_name

    def _get_compatible_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            timeout = self.timeout if self.timeout is not None else 60.0
            self._http_client = httpx.AsyncClient(timeout=timeout)
        return self._http_client

    def _build_compatible_headers(self) -> Dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.default_headers:
            headers.update(self.default_headers)
        if "anthropic-version" not in {key.lower(): value for key, value in headers.items()}:
            headers["anthropic-version"] = "2023-06-01"
        if self.api_key is not None:
            headers["x-api-key"] = self.api_key
        if self.auth_token is not None:
            headers["authorization"] = "Bearer %s" % self.auth_token
        return headers

    async def _generate_via_compatible_http(self, request: ModelRequest, model_name: str, tools: List[Dict[str, Any]]) -> ModelResponse:
        if self.base_url is None:
            raise RuntimeError("Compatible HTTP mode requires ANTHROPIC_BASE_URL.")
        client = self._get_compatible_http_client()
        url = self.base_url.rstrip("/") + "/v1/messages"
        payload: Dict[str, Any] = {
            "model": model_name,
            "system": request.instructions,
            "messages": self._build_messages(request),
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        response = await client.post(url, headers=self._build_compatible_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        raw_output = model_to_dict(data.get("content", []))
        parsed = self._parse_content_blocks(raw_output if isinstance(raw_output, list) else [])
        return ModelResponse(
            message=parsed.message,
            tool_calls=parsed.tool_calls,
            step_id=data.get("id"),
            metadata={"provider": "anthropic", "stop_reason": data.get("stop_reason"), "transport": "compatible_http"},
            raw_output=raw_output,
            usage=normalize_usage(data.get("usage", {})),
            response_id=data.get("id"),
        )

    def _parse_content_blocks(self, content_blocks: List[Dict[str, Any]]) -> ModelResponse:
        text_parts: List[str] = []
        tool_calls: List[ModelToolCall] = []
        for item in content_blocks:
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
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        client = self._get_client()
        model_name = resolve_request_model_name(request)
        if "/" in model_name:
            model_name = model_name.split("/", 1)[1]
        model_name = self.resolve_model_name(model_name)
        params: Dict[str, Any] = {
            "model": model_name,
            "system": request.instructions,
            "messages": self._build_messages(request),
            "max_tokens": self.max_tokens,
        }
        tools = self._build_tools(request)
        if tools:
            params["tools"] = tools

        if self._should_use_compatible_http():
            return await self._generate_via_compatible_http(request, model_name, tools)

        response = await client.messages.create(**params)
        raw_output = [model_to_dict(item) for item in getattr(response, "content", [])]
        parsed = self._parse_content_blocks(raw_output)

        return ModelResponse(
            message=parsed.message,
            tool_calls=parsed.tool_calls,
            step_id=getattr(response, "id", None),
            metadata={"provider": "anthropic", "stop_reason": getattr(response, "stop_reason", None), "transport": "sdk"},
            raw_output=raw_output,
            usage=normalize_usage(getattr(response, "usage", {})),
            response_id=getattr(response, "id", None),
        )
