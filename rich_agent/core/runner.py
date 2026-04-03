import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from .agent import Agent
from ..control.approvals import ApprovalDecision, ApprovalRequest
from .events import RunEvent
from .errors import ApprovalRequiredError, GuardrailTrippedError, PermissionDeniedError, RunTimeoutError
from ..control.guardrails import GuardrailConfig, GuardrailContext, GuardrailResult, GuardrailSpec
from ..runtime.harness import AgentHarness
from ..providers import AnthropicProvider, AzureProvider, OpenAIProvider
from ..providers.base import EchoModelProvider, ModelConfig, ModelRequest, ModelResponse
from .result import Artifact, CostBreakdown, MessageItem, RunResult, ToolCallRecord, UsageStats, UsageStep
from .run_config import RunConfig
from ..sessions import InMemorySession, Session
from ..control.tool import ToolContext, ToolRegistry, ToolSpec
from ..runtime.workspace import Workspace


def _estimate_tokens(value: Any) -> int:
    return max(1, len(str(value)) // 4) if value not in (None, "") else 0


async def _maybe_await(value: Any) -> Any:
    if asyncio.isfuture(value) or asyncio.iscoroutine(value):
        return await value
    return value


def _serialize(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


@dataclass
class RunContext:
    run_id: str
    agent: Agent
    config: RunConfig
    session: Session
    harness: AgentHarness
    workspace: Workspace
    messages: List[MessageItem] = field(default_factory=list)
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    todos: List[Any] = field(default_factory=list)
    trace_metadata: Dict[str, Any] = field(default_factory=dict)


class RunStream:
    def __init__(self, starter: Callable[["RunStream"], Any]) -> None:
        self._starter = starter
        self._queue: "asyncio.Queue[Optional[RunEvent]]" = asyncio.Queue()
        self._task: Optional["asyncio.Task[Any]"] = None
        self._result_future: "asyncio.Future[RunResult]" = asyncio.get_event_loop().create_future()
        self._approval_waiters: Dict[str, "asyncio.Future[ApprovalDecision]"] = {}

    def _ensure_started(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._starter(self))

    def __aiter__(self):
        self._ensure_started()
        return self

    async def __anext__(self) -> RunEvent:
        self._ensure_started()
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def emit(self, event: RunEvent) -> None:
        await self._queue.put(event)

    async def finish(self, result: RunResult) -> None:
        if not self._result_future.done():
            self._result_future.set_result(result)
        await self._queue.put(None)

    async def fail(self, exc: Exception) -> None:
        if not self._result_future.done():
            self._result_future.set_exception(exc)
        await self._queue.put(None)

    async def result(self) -> RunResult:
        self._ensure_started()
        return await self._result_future

    async def request_approval(self, approval: ApprovalRequest) -> ApprovalDecision:
        waiter: "asyncio.Future[ApprovalDecision]" = asyncio.get_event_loop().create_future()
        self._approval_waiters[approval.request_id] = waiter
        return await waiter

    async def respond_approval(self, request_id: str, decision: ApprovalDecision) -> None:
        waiter = self._approval_waiters.pop(request_id)
        if not waiter.done():
            waiter.set_result(decision)


class Runner:
    @classmethod
    async def run(cls, agent: Agent, input: Any, config: Optional[RunConfig] = None) -> RunResult:
        resolved = cls._resolve_config(config)
        try:
            if resolved.timeout is not None:
                return await asyncio.wait_for(
                    cls._execute(agent=agent, user_input=input, config=resolved, stream=None),
                    timeout=resolved.timeout.total_seconds(),
                )
            return await cls._execute(agent=agent, user_input=input, config=resolved, stream=None)
        except asyncio.TimeoutError as exc:
            raise RunTimeoutError("Run exceeded configured timeout.") from exc

    @classmethod
    def run_sync(cls, agent: Agent, input: Any, config: Optional[RunConfig] = None) -> RunResult:
        return asyncio.run(cls.run(agent=agent, input=input, config=config))

    @classmethod
    def run_stream(cls, agent: Agent, input: Any, config: Optional[RunConfig] = None) -> RunStream:
        resolved = cls._resolve_config(config)

        async def starter(stream: RunStream) -> None:
            try:
                if resolved.timeout is not None:
                    result = await asyncio.wait_for(
                        cls._execute(agent=agent, user_input=input, config=resolved, stream=stream),
                        timeout=resolved.timeout.total_seconds(),
                    )
                else:
                    result = await cls._execute(agent=agent, user_input=input, config=resolved, stream=stream)
                await stream.finish(result)
            except Exception as exc:
                await stream.fail(exc)

        return RunStream(starter=starter)

    @staticmethod
    def _resolve_config(config: Optional[RunConfig]) -> RunConfig:
        return config or RunConfig()

    @classmethod
    def _resolve_runtime(cls, agent: Agent, config: RunConfig) -> Tuple[Session, AgentHarness]:
        session = config.session or InMemorySession()
        harness = config.harness or AgentHarness(workspace=Workspace.local(str(Path.cwd())))
        return session, harness

    @classmethod
    def _resolve_model_provider(cls, agent: Agent, config: RunConfig) -> Tuple[str, Any]:
        model = config.model_override or agent.model
        if isinstance(model, ModelConfig):
            name = model.name or "configured"
            return name, model.provider or EchoModelProvider(name)
        if isinstance(model, str):
            if model.startswith("openai/"):
                return model.split("/", 1)[1], OpenAIProvider()
            if model.startswith("anthropic/"):
                return model.split("/", 1)[1], AnthropicProvider()
            if model.startswith("azure/"):
                return model.split("/", 1)[1], AzureProvider()
            return model, EchoModelProvider(model)
        return "configured", model

    @classmethod
    async def _emit(
        cls,
        stream: Optional[RunStream],
        run_id: str,
        agent_name: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if stream is None:
            return
        await stream.emit(
            RunEvent(
                event_id=uuid4().hex,
                type=event_type,
                run_id=run_id,
                agent_name=agent_name,
                timestamp=datetime.utcnow(),
                payload=_serialize(payload or {}),
            )
        )

    @classmethod
    async def _apply_input_guardrails(
        cls,
        guardrails: GuardrailConfig,
        value: Any,
        context: GuardrailContext,
        stream: Optional[RunStream],
        run_id: str,
        agent_name: str,
        records: List[GuardrailResult],
    ) -> Any:
        current = value
        for guardrail in guardrails.input:
            result = await _maybe_await(guardrail.fn(current, context))
            records.append(result)
            if result.action == "block":
                await cls._emit(
                    stream,
                    run_id,
                    agent_name,
                    "guardrail.tripped",
                    {"phase": "input", "reason": result.reason},
                )
                raise GuardrailTrippedError(result.reason or "Input blocked by guardrail.")
            if result.action == "rewrite":
                current = result.rewritten_value
        return current

    @classmethod
    async def _apply_output_guardrails(
        cls,
        guardrails: GuardrailConfig,
        value: Any,
        context: GuardrailContext,
        stream: Optional[RunStream],
        run_id: str,
        agent_name: str,
        records: List[GuardrailResult],
    ) -> Any:
        current = value
        for guardrail in guardrails.output:
            result = await _maybe_await(guardrail.fn(current, context))
            records.append(result)
            if result.action == "block":
                await cls._emit(
                    stream,
                    run_id,
                    agent_name,
                    "guardrail.tripped",
                    {"phase": "output", "reason": result.reason},
                )
                raise GuardrailTrippedError(result.reason or "Output blocked by guardrail.")
            if result.action == "rewrite":
                current = result.rewritten_value
        return current

    @classmethod
    async def _apply_tool_guardrails(
        cls,
        guardrails: GuardrailConfig,
        tool_name: str,
        arguments: Dict[str, Any],
        context: GuardrailContext,
        stream: Optional[RunStream],
        run_id: str,
        agent_name: str,
        records: List[GuardrailResult],
    ) -> Dict[str, Any]:
        current = dict(arguments)
        for guardrail in guardrails.tool:
            if guardrail.tools and not any(tool_name.startswith(pattern.rstrip("*")) for pattern in guardrail.tools):
                continue
            result = await _maybe_await(guardrail.fn(tool_name, current, context))
            records.append(result)
            if result.action == "block":
                await cls._emit(
                    stream,
                    run_id,
                    agent_name,
                    "guardrail.tripped",
                    {"phase": "tool", "reason": result.reason, "tool_name": tool_name},
                )
                raise GuardrailTrippedError(result.reason or "Tool blocked by guardrail.")
            if result.action == "rewrite" and isinstance(result.rewritten_value, dict):
                current = result.rewritten_value
        return current

    @classmethod
    async def _resolve_tool_approval(
        cls,
        stream: Optional[RunStream],
        harness: AgentHarness,
        run_id: str,
        agent_name: str,
        tool: ToolSpec,
        arguments: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        if not tool.permission.require_approval:
            return "not_required", arguments

        request = ApprovalRequest(
            request_id=uuid4().hex,
            run_id=run_id,
            tool_name=tool.name,
            tool_args=arguments,
            reason="Tool marked as approval required.",
            risk_level="high" if tool.permission.destructive else "medium",
        )

        if harness.approval_handler is not None:
            decision = await harness.approval_handler.request(request)
        elif stream is not None:
            await cls._emit(
                stream,
                run_id,
                agent_name,
                "tool.approval_required",
                {"request_id": request.request_id, "tool_name": tool.name, "tool_args": arguments},
            )
            decision = await stream.request_approval(request)
        else:
            raise ApprovalRequiredError("Tool approval required but no approval handler was configured.")

        if decision.action in ("deny", "timeout"):
            raise PermissionDeniedError("Tool approval denied.")
        if decision.action == "edit" and decision.updated_args is not None:
            return decision.action, decision.updated_args
        return decision.action, arguments

    @classmethod
    async def _invoke_tool(
        cls,
        run_context: RunContext,
        tool_registry: ToolRegistry,
        tool_call: Any,
        provider_name: Optional[str],
        arguments: Dict[str, Any],
        stream: Optional[RunStream],
        guardrail_records: List[GuardrailResult],
    ) -> ToolCallRecord:
        tool_name = tool_call.tool_name
        tool = tool_registry.get(tool_name)

        if tool.permission.allowed_roles:
            if not set(run_context.config.roles).intersection(set(tool.permission.allowed_roles)):
                raise PermissionDeniedError("Tool role check failed.")

        if run_context.agent.permission_scope and run_context.agent.permission_scope.tools:
            if tool_name not in run_context.agent.permission_scope.tools:
                raise PermissionDeniedError("Tool is outside the configured permission scope.")

        guardrail_context = GuardrailContext(
            run_id=run_context.run_id,
            agent_name=run_context.agent.name,
            metadata=run_context.trace_metadata,
        )
        if run_context.agent.guardrails:
            arguments = await cls._apply_tool_guardrails(
                run_context.agent.guardrails,
                tool_name,
                arguments,
                guardrail_context,
                stream,
                run_context.run_id,
                run_context.agent.name,
                guardrail_records,
            )

        approval_state, approved_args = await cls._resolve_tool_approval(
            stream=stream,
            harness=run_context.harness,
            run_id=run_context.run_id,
            agent_name=run_context.agent.name,
            tool=tool,
            arguments=arguments,
        )

        await cls._emit(
            stream,
            run_context.run_id,
            run_context.agent.name,
            "tool.call.started",
            {"tool_name": tool_name, "arguments": approved_args},
        )

        started = perf_counter()
        output = await tool.invoke(approved_args, context=ToolContext(run_context=run_context, workspace=run_context.workspace))
        duration_ms = (perf_counter() - started) * 1000.0
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=approved_args,
            call_id=getattr(tool_call, "call_id", None),
            output=output,
            duration_ms=duration_ms,
            approval=approval_state,
            provider=provider_name,
        )
        await cls._emit(
            stream,
            run_context.run_id,
            run_context.agent.name,
            "tool.call.completed",
            {"tool_name": tool_name, "output": output, "duration_ms": duration_ms},
        )
        return record

    @classmethod
    async def _execute(cls, agent: Agent, user_input: Any, config: RunConfig, stream: Optional[RunStream]) -> RunResult:
        session, harness = cls._resolve_runtime(agent, config)
        workspace = harness.workspace
        run_id = uuid4().hex
        started = perf_counter()
        guardrail_records: List[GuardrailResult] = []
        await cls._emit(stream, run_id, agent.name, "run.started", {"agent_name": agent.name})

        history = await session.get_history()
        loaded = await harness.load_context(session)
        await cls._emit(
            stream,
            run_id,
            agent.name,
            "context.loaded",
            {
                "memories": list(loaded.memories.keys()),
                "skills": [skill.name for skill in loaded.skills],
                "todo_count": len(loaded.todos),
            },
        )

        run_context = RunContext(
            run_id=run_id,
            agent=agent,
            config=config,
            session=session,
            harness=harness,
            workspace=workspace,
            messages=list(history),
            todos=list(loaded.todos),
            trace_metadata=dict(config.trace_metadata),
        )

        guardrails = agent.guardrails or GuardrailConfig()
        guardrail_context = GuardrailContext(
            run_id=run_id,
            agent_name=agent.name,
            metadata=config.trace_metadata,
        )
        current_input = await cls._apply_input_guardrails(
            guardrails,
            user_input,
            guardrail_context,
            stream,
            run_id,
            agent.name,
            guardrail_records,
        )

        new_messages: List[MessageItem] = [MessageItem(role="user", content=current_input)]
        all_messages = list(history) + list(new_messages)
        tool_registry = ToolRegistry(agent.tools)
        tool_records: List[ToolCallRecord] = []
        artifacts: List[Artifact] = []
        usage = UsageStats()
        final_output: Any = ""
        handoff_chain: List[str] = [agent.name]
        active_agent = agent

        max_turns = config.max_turns or agent.max_turns or 4
        for turn in range(max_turns):
            model_name, provider = cls._resolve_model_provider(active_agent, config)
            response = await provider.generate(
                ModelRequest(
                    agent=active_agent,
                    instructions=active_agent.resolve_instructions(run_context),
                    latest_input=current_input,
                    history=all_messages,
                    tool_results=tool_records,
                    available_tools=tool_registry.list(),
                    context=run_context,
                )
            )

            step_id = response.step_id or uuid4().hex
            usage.record_step(
                UsageStep(
                    step_id=step_id,
                    model=model_name,
                    input_tokens=response.usage.get("input_tokens", _estimate_tokens(current_input)),
                    output_tokens=response.usage.get("output_tokens", _estimate_tokens(response.message)),
                    cache_read_tokens=response.usage.get("cache_read_tokens", 0),
                    cache_write_tokens=response.usage.get("cache_write_tokens", 0),
                )
            )

            assistant_metadata = dict(response.metadata)
            if response.raw_output is not None:
                assistant_metadata["raw_output"] = response.raw_output
            if response.response_id is not None:
                assistant_metadata["response_id"] = response.response_id

            if response.message not in (None, "") or response.raw_output is not None:
                if response.message not in (None, ""):
                    final_output = response.message
                assistant_message = MessageItem(
                    role="assistant",
                    content=response.message or "",
                    name=active_agent.name,
                    metadata=assistant_metadata,
                )
                new_messages.append(assistant_message)
                all_messages.append(assistant_message)
                if response.message not in (None, ""):
                    await cls._emit(
                        stream,
                        run_id,
                        active_agent.name,
                        "message.delta",
                        {"text": str(response.message)},
                    )

            if response.handoff:
                matched = None
                for handoff in active_agent.handoffs:
                    if getattr(handoff.target, "name", None) == response.handoff:
                        matched = handoff
                        break
                if matched is not None:
                    await cls._emit(
                        stream,
                        run_id,
                        active_agent.name,
                        "handoff.started",
                        {"from_agent": active_agent.name, "to_agent": matched.target.name},
                    )
                    active_agent = matched.target
                    run_context.agent = active_agent
                    handoff_chain.append(active_agent.name)
                    continue

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                record = await cls._invoke_tool(
                    run_context=run_context,
                    tool_registry=tool_registry,
                    tool_call=tool_call,
                    provider_name=assistant_metadata.get("provider"),
                    arguments=tool_call.arguments,
                    stream=stream,
                    guardrail_records=guardrail_records,
                )
                tool_records.append(record)
                run_context.tool_calls.append(record)
                tool_message = MessageItem(
                    role="tool",
                    content=record.output,
                    name=record.tool_name,
                    metadata={
                        "tool_call_id": record.call_id,
                        "provider": assistant_metadata.get("provider"),
                    },
                )
                new_messages.append(tool_message)
                all_messages.append(tool_message)
                current_input = record.output
                if isinstance(record.output, Artifact):
                    artifacts.append(record.output)
                    await cls._emit(
                        stream,
                        run_id,
                        active_agent.name,
                        "artifact.created",
                        {"kind": record.output.kind, "path": record.output.path},
                    )

        final_output = await cls._apply_output_guardrails(
            guardrails,
            final_output,
            guardrail_context,
            stream,
            run_id,
            active_agent.name,
            guardrail_records,
        )

        await session.add_messages(new_messages)
        duration = timedelta(seconds=perf_counter() - started)
        result = RunResult(
            run_id=run_id,
            final_output=final_output,
            messages=list(history) + new_messages,
            usage=usage,
            cost=CostBreakdown.from_usage(usage),
            duration=duration,
            trace_id=run_id,
            session_id=session.session_id,
            todos=list(loaded.todos),
            artifacts=artifacts,
            guardrail_results=guardrail_records,
            tool_calls=tool_records,
            handoff_chain=handoff_chain,
            metadata={"skills": [skill.name for skill in loaded.skills], "memory_files": list(loaded.memories.keys())},
        )
        await cls._emit(
            stream,
            run_id,
            active_agent.name,
            "run.completed",
            {"final_output": final_output, "tool_calls": len(tool_records)},
        )
        return result
