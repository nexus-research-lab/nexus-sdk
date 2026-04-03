# Nexus SDK

基于 `rich-agent-sdk-specification-v1` 的 Python SDK 起步版本。

当前这版先把 v1 的执行骨架和公开 API 形状落下来，重点覆盖：

- `Agent` / `Runner` / `RunConfig` / `RunResult` / `RunEvent`
- `@tool` / `ToolRegistry` / `ToolPermission`
- `Session` 抽象与 `InMemorySession` / `SQLiteSession`
- `Workspace` / `AgentHarness` / `SandboxManager`
- `Guardrail` / `Approval` / `Router` / `Handoff` / `Subagent`
- `ModelConfig` 与可插拔 `ModelProvider` 接口

## Installation Extras

```sh
pip install -e '.[openai,anthropic,azure,sessions]'
```

如果你只需要一部分能力，也可以按需安装：

- `.[openai]`
- `.[anthropic]`
- `.[azure]`
- `.[sessions]`

## Environment Template

```sh
cp .env.example .env
```

`examples/provider_smoke.py` 会自动读取项目根目录下的 `.env`。

这不是一个“已经接好 OpenAI/Anthropic 全套 API”的成品版，而是一个可以继续往里填企业能力的基础 runtime。

## 目录

```text
nexus-sdk/
├── rich_agent/
│   ├── core/        # Agent / Runner / Event / Result / Error
│   ├── providers/   # OpenAI / Anthropic / Azure / Gateway
│   ├── runtime/     # Harness / Workspace / Sandbox / Hooks / Tracing
│   ├── control/     # Tool / Approval / Guardrail / Router / Handoff
│   ├── resources/   # MCP / Skill / Memory / Knowledge / Todo
│   ├── config/      # Permission / Quota / Tenancy
│   ├── sessions/    # Memory / SQLite / Redis / Postgres / Encrypted
│   └── *.py         # Backward-compatible re-export shims
├── examples/
└── tests/
```

实现已经按层拆开；顶层 `rich_agent/*.py` 主要用于兼容旧 import，不建议继续把新实现直接堆在根目录。

## Quickstart

```python
from rich_agent import Agent, ModelConfig, Runner, tool
from rich_agent.providers import ModelResponse, ModelToolCall


@tool(description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b


class DemoProvider:
    async def generate(self, request):
        if not request.tool_results:
            return ModelResponse(
                message="先调用工具",
                tool_calls=[ModelToolCall(tool_name="add", arguments={"a": 2, "b": 3})],
                step_id="step-1",
            )
        return ModelResponse(message=f"结果是 {request.tool_results[-1].output}", step_id="step-2")


agent = Agent(
    name="calculator",
    instructions="你是一个计算助手。",
    model=ModelConfig(name="demo", provider=DemoProvider()),
    tools=[add],
)

result = Runner.run_sync(agent, "帮我算一下 2 + 3")
print(result.final_output)
```

## Real Providers

```python
from rich_agent import Agent, ModelConfig, Runner
from rich_agent.providers import AnthropicProvider, AzureProvider, OpenAIProvider

openai_agent = Agent(
    name="openai-agent",
    instructions="You are a precise assistant.",
    model=ModelConfig(name="gpt-4.1", provider=OpenAIProvider()),
)

anthropic_agent = Agent(
    name="anthropic-agent",
    instructions="You are a precise assistant.",
    model=ModelConfig(name="claude-sonnet-4-5", provider=AnthropicProvider()),
)

azure_agent = Agent(
    name="azure-agent",
    instructions="You are a precise assistant.",
    model=ModelConfig(
        name="my-deployment",
        provider=AzureProvider(endpoint="https://YOUR-RESOURCE.openai.azure.com"),
    ),
)
```

也支持直接用带前缀的模型字符串：

- `openai/gpt-4.1`
- `anthropic/claude-sonnet-4-5`
- `azure/my-deployment`

也可以直接从环境变量构建 provider：

```python
from rich_agent.providers import AnthropicProvider, AzureProvider, OpenAIProvider

openai_provider = OpenAIProvider.from_env()
anthropic_provider = AnthropicProvider.from_env()
azure_provider = AzureProvider.from_env()
```

目前支持的环境变量：

- OpenAI: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`
- Anthropic: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_VERSION`
- Azure OpenAI: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_VERSION`, `AZURE_OPENAI_AD_TOKEN`, `AZURE_OPENAI_USE_ENTRA_ID`

对于 Anthropic 兼容网关，也支持从这些变量里取默认模型：

- `ANTHROPIC_MODEL`
- `ANTHROPIC_DEFAULT_SONNET_MODEL`
- `ANTHROPIC_REASONING_MODEL`

可以直接跑一个真实联调 smoke test：

```sh
PYTHONPATH=. python3 examples/provider_smoke.py --provider openai --model gpt-4.1
PYTHONPATH=. python3 examples/provider_smoke.py --provider anthropic --model claude-sonnet-4-20250514
PYTHONPATH=. python3 examples/provider_smoke.py --provider azure --model your-deployment-name
```

## Sessions

```python
from rich_agent import RunConfig, Runner
from rich_agent.sessions import EncryptedSession, PostgresSession, RedisSession, SQLiteSession

sqlite_session = SQLiteSession(path=".rich-agent/session.db", session_id="demo")
redis_session = RedisSession(url="redis://localhost:6379/0", session_id="demo")
postgres_session = PostgresSession(url="postgresql://user:pass@localhost:5432/app", session_id="demo")

key = EncryptedSession.generate_key()
secure_session = EncryptedSession(wrapped=sqlite_session, secret_key=key)

result = Runner.run_sync(agent, "hello", config=RunConfig(session=secure_session))
```

`RedisSession` 现在支持 `ttl_seconds`，`Session` 基类也提供了 `close()` 和 async context manager，便于在服务生命周期里显式释放连接。

## 现阶段边界

- 多 Provider 网关路由策略还没有做自动决策层，但三家 provider 已经具备真实 SDK 接入点。
- `run_stream()` 已支持事件流和审批回填，但首版没有接 WebSocket / HTTP transport。
- Redis / Postgres / Encrypted session 已补上基础实现，Redis 具备 TTL，Session 也支持显式 close；如果继续往生产推进，下一步适合补 migrations、连接池与后台清理策略。
