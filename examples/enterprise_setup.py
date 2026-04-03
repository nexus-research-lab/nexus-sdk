from rich_agent import Agent, ModelConfig, RunConfig, Runner
from rich_agent.models import OpenAIProvider
from rich_agent.sessions import SQLiteSession


def main() -> None:
    agent = Agent(
        name="enterprise-support",
        instructions="You are a strict enterprise support assistant.",
        model=ModelConfig(name="gpt-4.1", provider=OpenAIProvider()),
    )
    session = SQLiteSession(path=".rich-agent/session.db", session_id="enterprise-demo")
    result = Runner.run_sync(agent, "Summarize the current deployment state.", config=RunConfig(session=session))
    print(result.final_output)


if __name__ == "__main__":
    main()
