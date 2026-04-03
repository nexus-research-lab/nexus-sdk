import os
import json
import unittest
from unittest.mock import patch

from rich_agent.core.result import MessageItem
from rich_agent.providers import AnthropicProvider, AzureProvider, OpenAIProvider, none_if_blank
from rich_agent.sessions import RedisSession


class FakeRedisClient:
    def __init__(self) -> None:
        self.calls = []

    async def rpush(self, key, *values):
        self.calls.append(("rpush", key, list(values)))

    async def expire(self, key, ttl):
        self.calls.append(("expire", key, ttl))

    async def lrange(self, key, start, end):
        return []

    async def delete(self, key):
        self.calls.append(("delete", key))

    async def aclose(self):
        self.calls.append(("aclose",))


class SessionBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_redis_session_applies_ttl_and_closes_client(self) -> None:
        client = FakeRedisClient()
        session = RedisSession(client=client, ttl_seconds=120, session_id="demo")

        await session.add_messages([MessageItem(role="user", content="hello")])
        await session.close()

        self.assertEqual(client.calls[1], ("expire", session.redis_key, 120))
        self.assertEqual(client.calls[-1], ("aclose",))


class ProviderEnvTests(unittest.TestCase):
    def test_none_if_blank(self) -> None:
        self.assertIsNone(none_if_blank(""))
        self.assertIsNone(none_if_blank("   "))
        self.assertEqual(none_if_blank("abc"), "abc")

    def test_openai_provider_reads_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "https://example.com/v1"}, clear=False):
            provider = OpenAIProvider.from_env()
        self.assertEqual(provider.api_key, "k")
        self.assertEqual(provider.base_url, "https://example.com/v1")

    def test_anthropic_provider_reads_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "k2",
                "ANTHROPIC_AUTH_TOKEN": "t2",
                "ANTHROPIC_API_VERSION": "2023-06-01",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7",
            },
            clear=False,
        ):
            provider = AnthropicProvider.from_env()
        self.assertEqual(provider.api_key, "k2")
        self.assertEqual(provider.auth_token, "t2")
        self.assertEqual(provider.default_headers, {"anthropic-version": "2023-06-01"})
        self.assertEqual(provider.default_sonnet_model, "glm-4.7")

    def test_anthropic_provider_can_map_claude_aliases(self) -> None:
        provider = AnthropicProvider(
            default_sonnet_model="glm-4.7",
            default_opus_model="glm-5.1",
            default_haiku_model="glm-4.5-air",
        )
        self.assertEqual(provider.resolve_model_name("claude-sonnet-4-20250514"), "glm-4.7")
        self.assertEqual(provider.resolve_model_name("claude-opus-4-1"), "glm-5.1")
        self.assertEqual(provider.resolve_model_name("claude-haiku-3-5"), "glm-4.5-air")
        self.assertEqual(provider.resolve_model_name("glm-5"), "glm-5")

    def test_anthropic_provider_prefers_sdk_by_default_for_custom_base_url(self) -> None:
        provider = AnthropicProvider(base_url="https://open.bigmodel.cn/api/anthropic", auth_token="tok")
        self.assertFalse(provider._should_use_compatible_http())

    def test_anthropic_provider_can_force_compatible_http(self) -> None:
        provider = AnthropicProvider(
            base_url="https://open.bigmodel.cn/api/anthropic",
            auth_token="tok",
            use_compatible_http=True,
        )
        self.assertTrue(provider._should_use_compatible_http())

    def test_anthropic_provider_keeps_sdk_for_official_base_url(self) -> None:
        provider = AnthropicProvider(base_url="https://api.anthropic.com", api_key="key")
        self.assertFalse(provider._should_use_compatible_http())

    def test_azure_provider_reads_api_key_env(self) -> None:
        env = {
            "AZURE_OPENAI_API_KEY": "ak",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "OPENAI_API_VERSION": "preview",
        }
        with patch.dict(os.environ, env, clear=False):
            provider = AzureProvider.from_env()
        self.assertEqual(provider.api_key, "ak")
        self.assertEqual(provider.endpoint, "https://example.openai.azure.com")
        self.assertEqual(provider.api_version, "preview")

    def test_azure_provider_ignores_blank_ad_token(self) -> None:
        env = {
            "AZURE_OPENAI_API_KEY": "ak",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_AD_TOKEN": "",
            "AZURE_OPENAI_USE_ENTRA_ID": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            provider = AzureProvider.from_env()
        self.assertIsNone(provider.azure_ad_token)
        self.assertFalse(provider.use_azure_client)

    def test_azure_provider_uses_compatible_http_by_default(self) -> None:
        provider = AzureProvider(endpoint="https://example.openai.azure.com", api_key="ak")
        self.assertTrue(provider.use_compatible_http)


if __name__ == "__main__":
    unittest.main()
