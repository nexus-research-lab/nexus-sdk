import tempfile
import unittest
from pathlib import Path

from rich_agent import (
    Agent,
    AgentHarness,
    ApprovalDecision,
    MemoryFile,
    ModelConfig,
    RunConfig,
    Runner,
    ToolPermission,
    Workspace,
    tool,
)
from rich_agent.providers import ModelResponse, ModelToolCall
from rich_agent.sessions import EncryptedSession, InMemorySession, SQLiteSession


@tool(description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b


@tool(
    description="Delete a customer",
    permission=ToolPermission(require_approval=True, destructive=True),
)
def delete_customer(customer_id: str) -> str:
    return "deleted:%s" % customer_id


class ToolLoopProvider:
    async def generate(self, request):
        if not request.tool_results:
            return ModelResponse(
                message="calling add",
                tool_calls=[ModelToolCall(tool_name="add", arguments={"a": 2, "b": 3})],
                step_id="step-1",
            )
        return ModelResponse(message="sum=%s" % request.tool_results[-1].output, step_id="step-2")


class ApprovalProvider:
    async def generate(self, request):
        if not request.tool_results:
            return ModelResponse(
                tool_calls=[ModelToolCall(tool_name="delete_customer", arguments={"customer_id": "cust-1"})],
                step_id="step-1",
            )
        return ModelResponse(message=request.tool_results[-1].output, step_id="step-2")


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_executes_tool_loop(self) -> None:
        session = InMemorySession()
        agent = Agent(
            name="calculator",
            instructions="You are a calculator.",
            model=ModelConfig(name="demo", provider=ToolLoopProvider()),
            tools=[add],
        )

        result = await Runner.run(agent, "2+3", config=RunConfig(session=session))

        self.assertEqual(result.final_output, "sum=5")
        self.assertEqual(len(result.tool_calls), 1)
        history = await session.get_history()
        self.assertEqual(len(history), 4)

    async def test_stream_supports_approval_round_trip(self) -> None:
        agent = Agent(
            name="ops",
            instructions="You are an operator.",
            model=ModelConfig(name="approval-demo", provider=ApprovalProvider()),
            tools=[delete_customer],
        )

        stream = Runner.run_stream(agent, "delete customer")
        seen_types = []
        async for event in stream:
            seen_types.append(event.type)
            if event.type == "tool.approval_required":
                await stream.respond_approval(
                    request_id=event.payload["request_id"],
                    decision=ApprovalDecision(action="edit", updated_args={"customer_id": "cust-2"}),
                )

        result = await stream.result()
        self.assertIn("tool.approval_required", seen_types)
        self.assertEqual(result.final_output, "deleted:cust-2")

    async def test_harness_loads_memory_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "AGENTS.md").write_text("always-on rules", encoding="utf-8")
            harness = AgentHarness(
                workspace=Workspace.local(tmpdir),
                memory_files=[MemoryFile.project("AGENTS.md", kind="policy")],
            )
            agent = Agent(name="echo", instructions="echo", model="echo")
            result = await Runner.run(agent, "hello", config=RunConfig(harness=harness))
            self.assertIn("AGENTS.md", result.metadata["memory_files"][0])

    async def test_sqlite_session_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session = SQLiteSession(path=str(Path(tmpdir) / "session.db"), session_id="demo-session")
            agent = Agent(name="echo", instructions="echo", model="echo")
            first = await Runner.run(agent, "first", config=RunConfig(session=session))
            second = await Runner.run(agent, "second", config=RunConfig(session=session))
            history = await session.get_history()

            self.assertEqual(first.final_output, "first")
            self.assertEqual(second.final_output, "second")
            self.assertGreaterEqual(len(history), 4)

    async def test_encrypted_session_wraps_underlying_session(self) -> None:
        try:
            key = EncryptedSession.generate_key()
        except RuntimeError:
            self.skipTest("cryptography is not installed")
        wrapped = EncryptedSession(wrapped=InMemorySession(), secret_key=key)
        agent = Agent(name="echo", instructions="echo", model="echo")

        await Runner.run(agent, "secret", config=RunConfig(session=wrapped))

        plain_history = await wrapped.get_history()
        raw_history = await wrapped.wrapped.get_history()
        self.assertEqual(plain_history[0].content, "secret")
        self.assertNotEqual(raw_history[0].content, "secret")


if __name__ == "__main__":
    unittest.main()
