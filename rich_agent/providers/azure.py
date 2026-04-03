import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from .openai import OpenAIProvider
from .base import extract_openai_output_text, model_to_dict, none_if_blank, normalize_usage, resolve_request_model_name
from .base import ModelResponse, ModelToolCall


@dataclass
class AzureProvider(OpenAIProvider):
    endpoint: Optional[str] = None
    api_version: Optional[str] = None
    azure_ad_token: Optional[str] = None
    azure_ad_token_provider: Any = None
    use_azure_client: bool = False
    use_compatible_http: bool = True
    _client: Any = field(default=None, init=False, repr=False)
    _http_client: Any = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "AzureProvider":
        use_entra = none_if_blank(os.getenv("AZURE_OPENAI_USE_ENTRA_ID", ""))
        use_entra_bool = (use_entra or "").lower() in {"1", "true", "yes", "on"}
        endpoint = none_if_blank(os.getenv("AZURE_OPENAI_ENDPOINT"))
        api_version = none_if_blank(os.getenv("OPENAI_API_VERSION"))
        azure_ad_token = none_if_blank(os.getenv("AZURE_OPENAI_AD_TOKEN"))
        token_provider = None
        if use_entra_bool and azure_ad_token is None:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
        return cls(
            api_key=none_if_blank(os.getenv("AZURE_OPENAI_API_KEY")),
            endpoint=endpoint,
            api_version=api_version,
            azure_ad_token=azure_ad_token,
            azure_ad_token_provider=token_provider,
            use_azure_client=use_entra_bool or azure_ad_token is not None,
        )

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client
        if self._client is None:
            kwargs: Dict[str, Any] = {}
            base_url = self.base_url
            if base_url is None and self.endpoint is not None:
                base_url = self.endpoint.rstrip("/") + "/openai/v1/"
            if base_url is not None:
                kwargs["base_url"] = base_url
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            if self.api_version is not None:
                kwargs["api_version"] = self.api_version
            if self.timeout is not None:
                kwargs["timeout"] = self.timeout
            if self.max_retries is not None:
                kwargs["max_retries"] = self.max_retries
            if self.azure_ad_token_provider is not None:
                kwargs["azure_ad_token_provider"] = self.azure_ad_token_provider
            if self.azure_ad_token is not None:
                kwargs["azure_ad_token"] = self.azure_ad_token
            if self.use_azure_client or self.azure_ad_token_provider is not None or self.api_version is not None:
                from openai import AsyncAzureOpenAI

                self._client = AsyncAzureOpenAI(**kwargs)
            else:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            timeout = self.timeout if self.timeout is not None else 60.0
            self._http_client = httpx.AsyncClient(timeout=timeout)
        return self._http_client

    def _build_compatible_headers(self) -> Dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        elif self.azure_ad_token:
            headers["authorization"] = "Bearer %s" % self.azure_ad_token
        return headers

    async def _generate_via_compatible_http(self, request) -> ModelResponse:
        if self.endpoint is None and self.base_url is None:
            raise RuntimeError("Azure compatible HTTP mode requires AZURE_OPENAI_ENDPOINT or base_url.")

        url = self.base_url
        if url is None:
            url = self.endpoint.rstrip("/") + "/openai/v1/responses"

        model_name = resolve_request_model_name(request)
        if "/" in model_name:
            model_name = model_name.split("/", 1)[1]

        payload: Dict[str, Any] = {
            "model": model_name,
            "instructions": request.instructions,
            "input": self._build_input(request),
        }
        tools = self._build_tools(request)
        if tools:
            payload["tools"] = tools

        client = self._get_http_client()
        response = await client.post(url, headers=self._build_compatible_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        raw_output = [model_to_dict(item) for item in data.get("output", [])]
        tool_calls = []
        for item in raw_output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            arguments = item.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    import json

                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {"raw_arguments": arguments}
            tool_calls.append(
                ModelToolCall(
                    tool_name=str(item.get("name")),
                    arguments=arguments if isinstance(arguments, dict) else {"value": arguments},
                    call_id=item.get("call_id") or item.get("id"),
                )
            )
        return ModelResponse(
            message=data.get("output_text", "") or extract_openai_output_text(raw_output),
            tool_calls=tool_calls,
            step_id=data.get("id"),
            metadata={"provider": "azure", "transport": "compatible_http"},
            raw_output=raw_output,
            usage=normalize_usage(data.get("usage", {})),
            response_id=data.get("id"),
        )

    async def generate(self, request):
        if self.use_compatible_http and (self.endpoint is not None or self.base_url is not None):
            response = await self._generate_via_compatible_http(request)
        else:
            response = await super().generate(request)
        response.metadata["provider"] = "azure"
        return response

    async def close(self) -> None:
        await super().close()
        if self._http_client is not None:
            await self._http_client.aclose()
