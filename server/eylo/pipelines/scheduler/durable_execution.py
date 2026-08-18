"""Durable execution for one schedule-occurrence AgentRun."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from eylo.common.config import settings
from eylo.common.contracts.tool_availability import (
    ToolAvailabilityFacts,
    ToolRuntimeFact,
)
from eylo.common.database import get_transaction, start_transaction
from eylo.framework.agents.config import RunConfig
from eylo.framework.agents.context import RunContext, RunInput, RunMessage
from eylo.framework.agents.model import Model, ModelResponse
from eylo.framework.agents.result import RunResult, RunStatus
from eylo.framework.agents.runner import FrameworkRunner
from eylo.framework.agents.tool import ToolCall, ToolResult
from eylo.modules.agent_runs.domain import (
    AgentInputRequestKind,
    AgentRunLifecycle,
    AgentRunOriginKind,
    AgentRunOutcome,
)
from eylo.modules.agent_runs.service import (
    AgentRunWaitState,
    accept_agent_run_cancellation,
    fail_agent_run,
    finish_agent_run_in_transaction,
    load_agent_run_wait,
    pause_agent_run_in_transaction,
    resume_agent_run_in_transaction,
)
from eylo.modules.agent_runs.workflow import (
    AgentRunExecutionClaim,
    AgentRunWorkflowContext,
)
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.scheduler.models import ScheduleRevisionModel, ScheduleRunModel
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.pipelines.agent_run_tools import bind_agent_run_tool_command
from eylo.pipelines.agent_run_transcript import (
    AgentRunTranscript,
    AgentRunTranscriptBridge,
    PendingToolCallsModel,
    with_replay_messages,
)
from eylo.pipelines.agents import build_executable_agent_resolver
from eylo.pipelines.conversation.conversation_runner import ExistingConversationModel
from eylo.pipelines.conversation.domain import agent_spec_from_context
from eylo.pipelines.conversation.tool_executor import PlatformToolExecutor
from eylo.pipelines.system_tools.availability import (
    filter_available_system_tools,
    refresh_context_tool_availability,
)

if TYPE_CHECKING:
    from eylo.modules.agents.schemas.indb import AgentInDb
    from eylo.modules.tools.schemas.indb import ToolInDb

_HEARTBEAT_SECONDS = 120
_HEARTBEAT_INTERVAL_SECONDS = 30
_PAUSE_STATUSES = {
    RunStatus.WAITING_FOR_INPUT,
    RunStatus.WAITING_FOR_APPROVAL,
}


class ScheduledAgentRunInvalid(Exception):
    """A schedule-backed run no longer has valid immutable input."""


class ScheduledAgentRunRetryable(Exception):
    """A scheduled tool call is persisted but has no canonical result yet."""


class ScheduledAgentRunCancelled(Exception):
    """The exact schedule revision withdrew its filed work."""


@dataclass(slots=True)
class _ScheduledExecutionContext:
    """In-memory adapter context; it never creates a conversation or message row."""

    conversation: SimpleNamespace
    primary_agent: AgentInDb
    tools: list[ToolInDb]
    system_prompt: str
    principal_participant: SimpleNamespace
    agent_participant: SimpleNamespace
    messages: list
    handoff_agents: tuple[AgentInDb, ...] = ()
    widget_interfaces_enabled: bool = False
    external_id: str | None = None
    tool_availability: ToolAvailabilityFacts = field(
        default_factory=ToolAvailabilityFacts
    )

    def get_tools(self) -> list[ToolInDb]:
        return filter_available_system_tools(self.tools, self.tool_availability)

    def get_messages(self) -> list:
        return self.messages

    def get_primary_contact(self) -> SimpleNamespace:
        return self.principal_participant

    def get_primary_agent(self) -> SimpleNamespace:
        return self.agent_participant


class ScheduledFrameworkRunner:
    """Resolve exact agent authority and run one non-conversation framework turn."""

    def __init__(
        self,
        *,
        model_factory: Callable[[dict, RunConfig], Model] | None = None,
        tool_executor=None,
    ) -> None:
        self._model_factory = model_factory
        self._tool_executor = tool_executor or PlatformToolExecutor()

    async def run(
        self,
        *,
        claim: AgentRunExecutionClaim,
        workflow_context: AgentRunWorkflowContext,
        wait: AgentRunWaitState | None,
    ) -> RunResult:
        execution_context = await _build_execution_context(claim)
        await refresh_context_tool_availability(
            execution_context,
            runtime_facts=(
                ToolRuntimeFact.DURABLE_EXECUTION,
                ToolRuntimeFact.AGENT_RUN,
            ),
        )
        agent = agent_spec_from_context(execution_context)
        config = RunConfig(
            stream=False,
            prompt_caching=getattr(settings, "ENABLE_PROMPT_CACHING", False),
        )
        transcript = AgentRunTranscript(
            organization_id=claim.organization_id,
            agent_run_id=claim.run_id,
        )
        replay = await transcript.replay()
        run_input = with_replay_messages(
            _initial_run_input(claim, execution_context, agent.tools),
            replay,
        )
        if wait is not None:
            run_input = await self._resume_input(
                claim=claim,
                wait=wait,
                run_input=run_input,
                agent=agent,
                execution_context=execution_context,
                config=config,
                workflow_context=workflow_context,
                transcript=transcript,
                command_ids=replay.command_ids,
            )

        captured: dict[str, object] = {}

        local_context = {
            "conversation_context": execution_context,
            "agent_run_id": claim.run_id,
            "durable_context": workflow_context,
            "tool_use_messages": {},
        }
        bridge = AgentRunTranscriptBridge(
            transcript=transcript,
            local_context=local_context,
            command_ids=replay.command_ids,
        )

        async def capture_model_response(
            _context: RunContext,
            run_input: RunInput,
            response: ModelResponse,
            tool_calls: tuple[ToolCall, ...],
        ) -> None:
            captured["response"] = response
            captured["tool_calls"] = tool_calls
            await bridge.after_model_response(
                _context,
                run_input,
                response,
                tool_calls,
            )

        local_context.update(
            {
                "after_model_response": capture_model_response,
                "before_tool_call": bridge.before_tool_call,
                "after_tool_result": bridge.after_tool_result,
            }
        )
        base_model = (
            self._model_factory(local_context, config)
            if self._model_factory is not None
            else ExistingConversationModel(
                local_context,
                llm_resolver=build_llm_config_resolver(get_transaction()),
                model_config_overrides={
                    "prompt_caching": config.prompt_caching,
                },
                stream=False,
            )
        )
        model = PendingToolCallsModel(
            base_model,
            agent_run_id=claim.run_id,
            pending_calls=replay.pending_calls if wait is None else (),
        )
        runner = FrameworkRunner(
            model,
            tool_executor=self._tool_executor,
        )
        result = await runner.run(
            agent,
            run_input,
            config=config,
            local_context=local_context,
        )
        if result.status is RunStatus.FAILED:
            replay_after_failure = await transcript.replay()
            if replay_after_failure.pending_calls:
                raise ScheduledAgentRunRetryable(
                    "Persisted scheduled tool call requires durable replay."
                )
        await _persist_result(
            claim=claim,
            result=result,
            captured=captured,
        )
        return result

    async def _resume_input(
        self,
        *,
        claim: AgentRunExecutionClaim,
        wait: AgentRunWaitState,
        run_input: RunInput,
        agent,
        execution_context: _ScheduledExecutionContext,
        config: RunConfig,
        workflow_context: AgentRunWorkflowContext,
        transcript: AgentRunTranscript,
        command_ids: dict[str, UUID],
    ) -> RunInput:
        scheduled = wait.continuation.get("scheduled")
        if not isinstance(scheduled, dict):
            raise ScheduledAgentRunInvalid(
                "Scheduled AgentRun continuation is missing tool state."
            )
        try:
            call = ToolCall.model_validate(scheduled["tool_call"])
        except (KeyError, TypeError, ValueError) as error:
            raise ScheduledAgentRunInvalid(
                "Scheduled AgentRun continuation contains an invalid tool call."
            ) from error

        async def resolve_result() -> dict:
            if wait.kind is AgentInputRequestKind.APPROVAL:
                response = wait.response
                if not isinstance(response, dict):
                    raise ScheduledAgentRunInvalid(
                        "Approval response must be an object."
                    )
                if response.get("decision") == "reject":
                    result = ToolResult(
                        tool_call_id=call.id,
                        content="The user rejected this tool action.",
                        is_error=True,
                        metadata={"approval_rejected": True},
                    )
                elif response.get("decision") == "approve":
                    command_id = command_ids.get(call.id)
                    if command_id is None:
                        raise ScheduledAgentRunInvalid(
                            "Approved tool call has no durable command identity."
                        )
                    local_context = {
                        "conversation_context": execution_context,
                        "agent_run_id": claim.run_id,
                        "durable_context": workflow_context,
                        "tool_use_messages": {},
                    }
                    bind_agent_run_tool_command(
                        local_context,
                        call=call,
                        command_id=command_id,
                    )
                    result = await self._tool_executor.execute(
                        RunContext(
                            config=config,
                            current_agent=agent,
                            handoff_chain=[agent],
                            local_context=local_context,
                        ),
                        call,
                    )
                else:
                    raise ScheduledAgentRunInvalid(
                        "Approval decision must be approve or reject."
                    )
            else:
                result = ToolResult(
                    tool_call_id=call.id,
                    content=json.dumps(
                        wait.response,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    metadata={
                        "human_input_received": True,
                        "input_request_id": str(wait.request_id),
                    },
                )
            await transcript.record_tool_result(call, result)
            return {"recorded": True, "is_error": result.is_error}

        checkpointed = await workflow_context.step(
            key=f"resume:{wait.request_id}",
            version=1,
            operation=resolve_result,
        )
        if (
            not isinstance(checkpointed, dict)
            or checkpointed.get("recorded") is not True
        ):
            raise ScheduledAgentRunInvalid(
                "Scheduled AgentRun resume receipt is invalid."
            )
        tool_result = await transcript.tool_result(call)
        if tool_result is None:
            raise ScheduledAgentRunInvalid(
                "Scheduled AgentRun resume result is unavailable."
            )
        return _append_resumed_tool_exchange(run_input, call, tool_result)


class ScheduledAgentRunExecutor:
    """Execute schedule-origin claims and preserve AgentRun wait semantics."""

    def __init__(
        self,
        *,
        runner_factory: Callable[[], ScheduledFrameworkRunner] | None = None,
    ) -> None:
        self._runner_factory = runner_factory or ScheduledFrameworkRunner

    async def execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None:
        try:
            await _validate_occurrence(claim)
        except ScheduledAgentRunCancelled:
            await accept_agent_run_cancellation(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
            )
            return
        except ScheduledAgentRunInvalid:
            await fail_agent_run(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
                failure_summary="scheduled_agent_run_invalid",
            )
            return

        wait = await load_agent_run_wait(
            organization_id=claim.organization_id,
            run_id=claim.run_id,
        )
        while True:
            if wait is not None:
                event_payload = await context.await_event(
                    event_name=wait.event_name,
                    key=wait.resume_step_key,
                    version=1,
                )
                _validate_resume_event(event_payload, claim=claim, wait=wait)

            result_holder: list[RunResult] = []

            async def execute_turn() -> None:
                async with start_transaction() as session:
                    resumed_wait = None
                    if wait is not None:
                        resumed_wait = await resume_agent_run_in_transaction(
                            session,
                            organization_id=claim.organization_id,
                            run_id=claim.run_id,
                            request_id=wait.request_id,
                        )
                    result_holder.append(
                        await self._runner_factory().run(
                            claim=claim,
                            workflow_context=context,
                            wait=resumed_wait,
                        )
                    )

            await _run_with_heartbeat(context, execute_turn)
            result = result_holder[0]
            if result.status not in _PAUSE_STATUSES:
                return
            wait = await load_agent_run_wait(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
            )
            if wait is None:
                raise ScheduledAgentRunInvalid(
                    "Paused scheduled AgentRun has no durable input request."
                )


async def _build_execution_context(
    claim: AgentRunExecutionClaim,
) -> _ScheduledExecutionContext:
    resolver = build_executable_agent_resolver(get_transaction())
    resolved = await resolver.resolve_exact(
        organization_id=claim.organization_id,
        agent_id=claim.agent_id,
        revision=claim.agent_revision,
        consumer_kind=TemplateConsumerKind.BACKGROUND_AGENT,
    )
    conversation = SimpleNamespace(
        id=claim.origin_schedule_run_id,
        organization_id=claim.organization_id,
        swarm_id=None,
        swarm_revision=None,
        channel=None,
        meta={},
    )
    return _ScheduledExecutionContext(
        conversation=conversation,
        primary_agent=resolved.agent,
        tools=list(resolved.tools),
        system_prompt=resolved.system_prompt
        or resolved.agent.description
        or resolved.agent.name,
        principal_participant=SimpleNamespace(
            id=claim.principal.principal_id,
            entity_id=str(claim.principal.principal_id),
        ),
        agent_participant=SimpleNamespace(
            id=claim.agent_id,
            entity_id=str(claim.agent_id),
            agent_id=claim.agent_id,
            agent_revision=claim.agent_revision,
        ),
        messages=[],
    )


def _initial_run_input(claim, execution_context, tools) -> RunInput:
    return RunInput(
        instructions=execution_context.system_prompt,
        messages=(
            RunMessage(
                role="user",
                content=claim.goal,
                metadata={
                    "organization_id": str(claim.organization_id),
                    "schedule_run_id": str(claim.origin_schedule_run_id),
                    "request_id": str(claim.origin_schedule_run_id),
                },
            ),
        ),
        tools=tools,
        metadata={
            "organization_id": str(claim.organization_id),
            "schedule_run_id": str(claim.origin_schedule_run_id),
            "request_id": str(claim.origin_schedule_run_id),
        },
    )


def _append_resumed_tool_exchange(
    run_input: RunInput,
    call: ToolCall,
    result: ToolResult,
) -> RunInput:
    request_id = run_input.metadata.get("request_id")
    content = (
        result.content
        if isinstance(result.content, str)
        else json.dumps(result.content, ensure_ascii=False, separators=(",", ":"))
    )
    messages = (
        *run_input.messages,
        RunMessage(
            role="assistant",
            content=f"Tool call: {call.name}",
            metadata={
                "request_id": request_id,
                "tool_call": {
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                },
            },
        ),
        RunMessage(
            role="tool",
            content=content,
            metadata={
                "request_id": request_id,
                "tool_result": {
                    "tool_call_id": result.tool_call_id,
                    "name": call.name,
                    "is_error": result.is_error,
                    "content": result.content,
                },
            },
        ),
    )
    return run_input.model_copy(update={"messages": messages})


async def _persist_result(
    *,
    claim: AgentRunExecutionClaim,
    result: RunResult,
    captured: dict[str, object],
) -> None:
    if result.status in _PAUSE_STATUSES:
        kind, prompt, expected_schema, continuation = _pause_fields(result, captured)
        await pause_agent_run_in_transaction(
            get_transaction(),
            organization_id=claim.organization_id,
            run_id=claim.run_id,
            kind=kind,
            prompt=prompt,
            expected_response_schema=expected_schema,
            continuation=continuation,
        )
        return

    lifecycle, outcome, run_result, reason, failure = _terminal_fields(claim, result)
    await finish_agent_run_in_transaction(
        get_transaction(),
        organization_id=claim.organization_id,
        run_id=claim.run_id,
        lifecycle=lifecycle,
        outcome=outcome,
        result=run_result,
        outcome_reason=reason,
        failure_summary=failure,
    )


def _pause_fields(
    result: RunResult,
    captured: dict[str, object],
) -> tuple[AgentInputRequestKind, str, dict, dict]:
    framework = result.metadata.get("continuation")
    if not isinstance(framework, dict):
        raise ScheduledAgentRunInvalid(
            "Framework pause is missing continuation metadata."
        )
    calls = captured.get("tool_calls")
    if not isinstance(calls, tuple):
        raise ScheduledAgentRunInvalid("Framework pause has no captured tool call.")
    call = next(
        (
            candidate
            for candidate in calls
            if isinstance(candidate, ToolCall)
            and candidate.id == framework.get("tool_call_id")
        ),
        None,
    )
    if call is None:
        raise ScheduledAgentRunInvalid(
            "Framework pause continuation differs from its tool call."
        )

    if result.status is RunStatus.WAITING_FOR_APPROVAL:
        request = result.metadata.get("approval_request")
        if not isinstance(request, dict):
            raise ScheduledAgentRunInvalid(
                "Approval pause is missing request metadata."
            )
        kind = AgentInputRequestKind.APPROVAL
        prompt = str(
            request.get("action_summary")
            or request.get("policy_reason")
            or "Approve this scheduled agent action?"
        )
        expected_schema = {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["approve", "reject"]},
                "comment": {"type": "string"},
            },
            "required": ["decision"],
            "additionalProperties": False,
        }
    elif result.status is RunStatus.WAITING_FOR_INPUT:
        request = result.metadata.get("input_request")
        if not isinstance(request, dict):
            raise ScheduledAgentRunInvalid("Input pause is missing request metadata.")
        kind = AgentInputRequestKind.INPUT
        prompt = str(request.get("prompt") or "Provide the requested information.")
        expected_schema = request.get("expected_input_schema") or {}
        if not isinstance(expected_schema, dict):
            raise ScheduledAgentRunInvalid("Input response schema must be an object.")
    else:
        raise ScheduledAgentRunInvalid("Framework result is not a pause.")

    return (
        kind,
        prompt,
        expected_schema,
        {
            "framework": framework,
            "request": request,
            "scheduled": {"tool_call": call.model_dump(mode="json")},
        },
    )


def _terminal_fields(
    claim: AgentRunExecutionClaim,
    result: RunResult,
) -> tuple[
    AgentRunLifecycle,
    AgentRunOutcome,
    dict | None,
    str | None,
    str | None,
]:
    if result.status is RunStatus.COMPLETED:
        return (
            AgentRunLifecycle.COMPLETED,
            AgentRunOutcome.ACHIEVED,
            _run_result(claim, result),
            None,
            None,
        )
    if result.status in {RunStatus.TIMED_OUT, RunStatus.MAX_TURNS_EXCEEDED}:
        reason = f"Scheduled agent execution ended with {result.status.value}."
        return (
            AgentRunLifecycle.COMPLETED,
            AgentRunOutcome.EXHAUSTED,
            _run_result(claim, result),
            reason,
            None,
        )
    return (
        AgentRunLifecycle.FAILED,
        AgentRunOutcome.FAILED,
        None,
        None,
        f"Scheduled agent execution ended with {result.status.value}.",
    )


def _run_result(claim: AgentRunExecutionClaim, result: RunResult) -> dict:
    projected = {
        "kind": "scheduled_agent",
        "schedule_run_id": str(claim.origin_schedule_run_id),
        "framework_run_id": str(result.run_id),
        "framework_status": result.status.value,
        "output": result.final_output,
        "usage": result.usage.model_dump(mode="json"),
    }
    if len(json.dumps(projected, separators=(",", ":")).encode("utf-8")) > 65536:
        raise ScheduledAgentRunInvalid(
            "Scheduled agent result exceeds the canonical 65536-byte limit."
        )
    return projected


async def _validate_occurrence(claim: AgentRunExecutionClaim) -> None:
    if (
        claim.origin_kind is not AgentRunOriginKind.SCHEDULE_OCCURRENCE
        or claim.origin_schedule_run_id is None
    ):
        raise ScheduledAgentRunInvalid(
            "Scheduled execution requires a schedule occurrence origin."
        )
    async with start_transaction(ro=True) as session:
        occurrence = await session.scalar(
            select(ScheduleRunModel).where(
                ScheduleRunModel.id == claim.origin_schedule_run_id,
                ScheduleRunModel.organization_id == claim.organization_id,
                ScheduleRunModel.deleted.is_(False),
            )
        )
        if occurrence is None:
            raise ScheduledAgentRunInvalid("Schedule occurrence is unavailable.")
        revision = await session.scalar(
            select(ScheduleRevisionModel).where(
                ScheduleRevisionModel.schedule_id == occurrence.schedule_id,
                ScheduleRevisionModel.revision == occurrence.schedule_revision,
                ScheduleRevisionModel.organization_id == claim.organization_id,
                ScheduleRevisionModel.deleted.is_(False),
            )
        )
    if revision is None or revision.availability != "published":
        raise ScheduledAgentRunCancelled
    if (
        occurrence.agent_id != claim.agent_id
        or occurrence.agent_revision != claim.agent_revision
        or claim.context_manifest.get("schedule_run_id") != str(occurrence.id)
        or claim.context_manifest.get("schedule_id") != str(occurrence.schedule_id)
        or claim.context_manifest.get("schedule_revision")
        != occurrence.schedule_revision
    ):
        raise ScheduledAgentRunInvalid(
            "AgentRun does not match its immutable schedule occurrence."
        )


def _validate_resume_event(
    payload: object,
    *,
    claim: AgentRunExecutionClaim,
    wait: AgentRunWaitState,
) -> None:
    expected = {
        "organization_id": str(claim.organization_id),
        "run_id": str(claim.run_id),
        "request_id": str(wait.request_id),
    }
    if payload != expected:
        raise ScheduledAgentRunInvalid(
            "Durable input event does not match the identified request."
        )


async def _run_with_heartbeat(
    context: AgentRunWorkflowContext,
    operation: Callable[[], Awaitable[None]],
) -> None:
    operation_task = asyncio.create_task(operation())
    try:
        while not operation_task.done():
            remaining_milliseconds = await context.heartbeat(seconds=_HEARTBEAT_SECONDS)
            try:
                await asyncio.wait_for(
                    asyncio.shield(operation_task),
                    timeout=min(
                        _HEARTBEAT_INTERVAL_SECONDS,
                        max(0.001, remaining_milliseconds / 1000),
                    ),
                )
            except TimeoutError:
                continue
        await operation_task
    finally:
        if not operation_task.done():
            operation_task.cancel()
            try:
                await operation_task
            except asyncio.CancelledError:
                pass


__all__ = ["ScheduledAgentRunExecutor", "ScheduledFrameworkRunner"]
