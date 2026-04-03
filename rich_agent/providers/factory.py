import os
from dataclasses import dataclass
from typing import Optional, Tuple

from .anthropic import AnthropicProvider
from .azure import AzureProvider
from .base import ModelConfig, none_if_blank
from .openai import OpenAIProvider


ProviderKind = str


@dataclass(frozen=True)
class ProviderSelection:
    provider_kind: ProviderKind
    model_name: str


def parse_provider_model(model: str) -> ProviderSelection:
    if "/" in model:
        provider_kind, model_name = model.split("/", 1)
        return ProviderSelection(provider_kind=provider_kind, model_name=model_name)
    return ProviderSelection(provider_kind="raw", model_name=model)


def get_default_provider_kind() -> ProviderKind:
    if none_if_blank(os.getenv("OPENAI_API_KEY")):
        return "openai"
    if none_if_blank(os.getenv("ANTHROPIC_API_KEY")) or none_if_blank(os.getenv("ANTHROPIC_AUTH_TOKEN")):
        return "anthropic"
    if none_if_blank(os.getenv("AZURE_OPENAI_API_KEY")) or none_if_blank(os.getenv("AZURE_OPENAI_AD_TOKEN")):
        return "azure"
    return "echo"


def get_default_model_for_provider(provider_kind: ProviderKind) -> str:
    if provider_kind == "openai":
        return none_if_blank(os.getenv("OPENAI_MODEL")) or "gpt-4.1"
    if provider_kind == "anthropic":
        return (
            none_if_blank(os.getenv("ANTHROPIC_MODEL"))
            or none_if_blank(os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL"))
            or none_if_blank(os.getenv("ANTHROPIC_REASONING_MODEL"))
            or "claude-sonnet-4-5"
        )
    if provider_kind == "azure":
        return none_if_blank(os.getenv("AZURE_OPENAI_MODEL")) or "gpt-4.1"
    return "echo"


def create_provider_from_env(provider_kind: ProviderKind):
    if provider_kind == "openai":
        return OpenAIProvider.from_env()
    if provider_kind == "anthropic":
        return AnthropicProvider.from_env()
    if provider_kind == "azure":
        return AzureProvider.from_env()
    return None


def resolve_model_config(model: Optional[str] = None) -> Tuple[str, object]:
    if model:
        selection = parse_provider_model(model)
        provider = None if selection.provider_kind == "raw" else create_provider_from_env(selection.provider_kind)
        return selection.model_name, provider

    provider_kind = get_default_provider_kind()
    provider = create_provider_from_env(provider_kind)
    return get_default_model_for_provider(provider_kind), provider


def model_config_from_env(model: Optional[str] = None) -> ModelConfig:
    model_name, provider = resolve_model_config(model)
    return ModelConfig(name=model_name, provider=provider)
