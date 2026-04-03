import unittest

from rich_agent import Agent, ModelConfig, MessageItem
from rich_agent.providers import AnthropicProvider, OpenAIProvider


class FakeOpenAIResponses:
    def __init__(self) -> None:
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeOpenAIResponse()


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeOpenAIResponses()


class FakeOpenAIResponse:
    id = "resp_1"
    output_text = "Tool result received"
    output = [
        {
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_1",
            "name": "add",
            "arguments": "{\"a\": 2, \"b\": 3}",
        }
    ]
    usage = {"input_tokens": 11, "output_tokens": 7}


class FakeAnthropicMessages:
    def __init__(self) -> None:
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeAnthropicResponse()


class FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = FakeAnthropicMessages()


class FakeAnthropicResponse:
    id = "msg_1"
    stop_reason = "tool_use"
    content = [
        {"type": "text", "text": "Calling tool"},
        {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"query": "abc"}},
    ]
    usage = {"input_tokens": 21, "output_tokens": 9}


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_provider_builds_function_tools_and_parses_output(self) -> None:
        from rich_agent import tool
        from rich_agent.providers import ModelRequest

        @tool(description="Add two integers")
        def add(a: int, b: int) -> int:
            return a + b

        client = FakeOpenAIClient()
        provider = OpenAIProvider(client=client)
        agent = Agent(name="calc", instructions="calc", model="openai/gpt-4.1", tools=[add])
        request = ModelRequest(
            agent=agent,
            instructions="You are a calculator",
            latest_input="2+3",
            history=[MessageItem(role="user", content="2+3")],
            available_tools=[add],
        )

        response = await provider.generate(request)

        self.assertEqual(response.message, "Tool result received")
        self.assertEqual(response.tool_calls[0].tool_name, "add")
        self.assertEqual(response.tool_calls[0].call_id, "call_1")
        self.assertEqual(client.responses.calls[0]["tools"][0]["type"], "function")
        self.assertEqual(response.usage["input_tokens"], 11)

    async def test_openai_provider_uses_model_config_name(self) -> None:
        from rich_agent.providers import ModelConfig, ModelRequest

        client = FakeOpenAIClient()
        provider = OpenAIProvider(client=client)
        agent = Agent(name="calc", instructions="calc", model=ModelConfig(name="gpt-5.4", provider=provider))
        request = ModelRequest(agent=agent, instructions="hi", latest_input="hello")

        await provider.generate(request)

        self.assertEqual(client.responses.calls[0]["model"], "gpt-5.4")

    async def test_anthropic_provider_formats_tool_result_messages(self) -> None:
        from rich_agent import tool
        from rich_agent.providers import ModelRequest

        @tool(description="Lookup data")
        def lookup(query: str) -> str:
            return query

        client = FakeAnthropicClient()
        provider = AnthropicProvider(client=client)
        agent = Agent(name="lookup", instructions="lookup", model="anthropic/claude-sonnet-4", tools=[lookup])
        request = ModelRequest(
            agent=agent,
            instructions="You are a lookup assistant",
            latest_input="abc",
            history=[
                MessageItem(
                    role="assistant",
                    content="",
                    metadata={
                        "provider": "anthropic",
                        "raw_output": [{"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"query": "abc"}}],
                    },
                ),
                MessageItem(role="tool", content={"ok": True}, name="lookup", metadata={"tool_call_id": "toolu_1"}),
            ],
            available_tools=[lookup],
        )

        response = await provider.generate(request)

        sent_messages = client.messages.calls[0]["messages"]
        self.assertEqual(sent_messages[1]["content"][0]["type"], "tool_result")
        self.assertEqual(response.tool_calls[0].call_id, "toolu_1")
        self.assertEqual(response.metadata["provider"], "anthropic")


if __name__ == "__main__":
    unittest.main()
