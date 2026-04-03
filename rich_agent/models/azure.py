from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .openai import OpenAIProvider


@dataclass
class AzureProvider(OpenAIProvider):
    endpoint: Optional[str] = None
    api_version: Optional[str] = None
    azure_ad_token_provider: Any = None
    use_azure_client: bool = False
    _client: Any = field(default=None, init=False, repr=False)

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
            if self.use_azure_client or self.azure_ad_token_provider is not None or self.api_version is not None:
                from openai import AsyncAzureOpenAI

                self._client = AsyncAzureOpenAI(**kwargs)
            else:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def generate(self, request):
        response = await super().generate(request)
        response.metadata["provider"] = "azure"
        return response
