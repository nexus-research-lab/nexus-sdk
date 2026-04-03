import argparse
import asyncio
from pathlib import Path
import os
import sys

from rich_agent import Agent, ModelConfig, Runner
from rich_agent.providers import AnthropicProvider, AzureProvider, OpenAIProvider


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key not in os.environ or not os.environ.get(key):
            os.environ[key] = value


def build_provider(name: str):
    if name == "openai":
        return OpenAIProvider.from_env(), os.getenv("OPENAI_MODEL", "gpt-4.1")
    if name == "anthropic":
        return AnthropicProvider.from_env(), (
            os.getenv("ANTHROPIC_MODEL")
            or os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL")
            or os.getenv("ANTHROPIC_REASONING_MODEL")
            or "claude-sonnet-4-20250514"
        )
    if name == "azure":
        return AzureProvider.from_env(), os.getenv("AZURE_OPENAI_MODEL", "gpt-4.1")
    raise ValueError("Unsupported provider: %s" % name)


def explain_error(provider_name: str, model_name: str, exc: Exception) -> int:
    text = str(exc)
    print("Smoke test failed.", file=sys.stderr)
    print("provider=%s model=%s" % (provider_name, model_name), file=sys.stderr)
    print(text, file=sys.stderr)

    if provider_name == "azure" and "DeploymentNotFound" in text:
        print(
            "Hint: AZURE_OPENAI_MODEL must be your Azure deployment name, not the base model family name.",
            file=sys.stderr,
        )
    elif provider_name == "azure" and "Connection error" in text:
        print(
            "Hint: verify AZURE_OPENAI_ENDPOINT, outbound network access, and whether the resource is reachable.",
            file=sys.stderr,
        )
    elif provider_name == "anthropic" and ("模型不存在" in text or "model" in text.lower()):
        print(
            "Hint: this endpoint looks Anthropic-compatible but not Anthropic-official; use the provider's supported model code.",
            file=sys.stderr,
        )
        print(
            "If this is a Claude-compatible gateway, prefer the exact model code that works in your Claude env, for example ANTHROPIC_MODEL or ANTHROPIC_DEFAULT_SONNET_MODEL.",
            file=sys.stderr,
        )
    return 1


async def main() -> None:
    load_local_env()
    parser = argparse.ArgumentParser(description="Run a simple live provider smoke test.")
    parser.add_argument("--provider", choices=["openai", "anthropic", "azure"], required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt", default=os.getenv("SMOKE_PROMPT", "Reply with the word READY."))
    args = parser.parse_args()

    provider, default_model = build_provider(args.provider)
    model_name = args.model or default_model
    agent = Agent(
        name="%s-smoke" % args.provider,
        instructions="Return a concise answer.",
        model=ModelConfig(name=model_name, provider=provider),
    )
    try:
        result = await Runner.run(agent, args.prompt)
        print(result.final_output)
        return
    except Exception as exc:
        raise SystemExit(explain_error(args.provider, model_name, exc))
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
