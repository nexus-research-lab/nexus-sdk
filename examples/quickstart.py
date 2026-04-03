from rich_agent import Agent, ModelConfig, Runner, tool
from rich_agent.providers import ModelResponse, ModelToolCall


@tool(description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b


class DemoProvider:
    async def generate(self, request):
        if not request.tool_results:
            return ModelResponse(
                message="Calling add",
                tool_calls=[ModelToolCall(tool_name="add", arguments={"a": 2, "b": 3})],
                step_id="step-1",
            )
        return ModelResponse(message="Result: %s" % request.tool_results[-1].output, step_id="step-2")


def main() -> None:
    agent = Agent(
        name="calculator",
        instructions="You are a deterministic calculator assistant.",
        model=ModelConfig(name="demo", provider=DemoProvider()),
        tools=[add],
    )
    result = Runner.run_sync(agent, "What is 2 + 3?")
    print(result.final_output)


if __name__ == "__main__":
    main()
