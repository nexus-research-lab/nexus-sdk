# Rich Agent SDK

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

这不是一个“已经接好 OpenAI/Anthropic 全套 API”的成品版，而是一个可以继续往里填企业能力的基础 runtime。

## 目录

```text
nexus-sdk/
├── rich_agent/
├── examples/
└── tests/
```

## Quickstart

```python
from rich_agent import Agent, ModelConfig, Runner, tool
from rich_agent.models import ModelResponse, ModelToolCall


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
from rich_agent.models import AnthropicProvider, AzureProvider, OpenAIProvider

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

## 现阶段边界

- 多 Provider 网关路由策略还没有做自动决策层，但三家 provider 已经具备真实 SDK 接入点。
- `run_stream()` 已支持事件流和审批回填，但首版没有接 WebSocket / HTTP transport。
- Redis / Postgres / Encrypted session 已补上基础实现；生产级连接池、迁移和 TTL 策略还可以继续往深做。
