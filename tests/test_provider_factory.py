import os
import unittest
from unittest.mock import patch

from rich_agent.providers import (
    AnthropicProvider,
    AzureProvider,
    OpenAIProvider,
    create_provider_from_env,
    get_default_model_for_provider,
    get_default_provider_kind,
    model_config_from_env,
    parse_provider_model,
    resolve_model_config,
)


class ProviderFactoryTests(unittest.TestCase):
    def test_parse_provider_model_with_prefix(self) -> None:
        selection = parse_provider_model("anthropic/claude-sonnet-4-5")
        self.assertEqual(selection.provider_kind, "anthropic")
        self.assertEqual(selection.model_name, "claude-sonnet-4-5")

    def test_parse_provider_model_without_prefix_keeps_raw(self) -> None:
        selection = parse_provider_model("echo")
        self.assertEqual(selection.provider_kind, "raw")
        self.assertEqual(selection.model_name, "echo")

    def test_default_provider_kind_prefers_openai_then_anthropic_then_azure(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k1", "ANTHROPIC_API_KEY": "k2", "AZURE_OPENAI_API_KEY": "k3"}, clear=True):
            self.assertEqual(get_default_provider_kind(), "openai")
        with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "t2", "AZURE_OPENAI_API_KEY": "k3"}, clear=True):
            self.assertEqual(get_default_provider_kind(), "anthropic")
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "k3"}, clear=True):
            self.assertEqual(get_default_provider_kind(), "azure")

    def test_default_model_for_provider_uses_env(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-turbo"}, clear=True):
            self.assertEqual(get_default_model_for_provider("anthropic"), "glm-5-turbo")

    def test_create_provider_from_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k1"}, clear=True):
            self.assertIsInstance(create_provider_from_env("openai"), OpenAIProvider)
        with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "t2"}, clear=True):
            self.assertIsInstance(create_provider_from_env("anthropic"), AnthropicProvider)
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "k3"}, clear=True):
            self.assertIsInstance(create_provider_from_env("azure"), AzureProvider)

    def test_resolve_model_config(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "t2"}, clear=True):
            model_name, provider = resolve_model_config("anthropic/glm-5.1")
        self.assertEqual(model_name, "glm-5.1")
        self.assertIsInstance(provider, AnthropicProvider)

    def test_model_config_from_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k1", "OPENAI_MODEL": "gpt-5.4"}, clear=True):
            config = model_config_from_env()
        self.assertEqual(config.name, "gpt-5.4")
        self.assertIsInstance(config.provider, OpenAIProvider)


if __name__ == "__main__":
    unittest.main()
