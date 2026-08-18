"""Published-agent framework execution for direct objective AgentRuns."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from eylo.common.config import settings
from eylo.common.contracts.sandbox import SandboxError
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
from eylo.framework.agents.tool import (
    ToolCall,
    ToolExecutor,
    ToolKind,
    ToolResult,
    ToolSpec,
)
from eylo.modules.agent_runs.domain import (
    AgentInputRequestKind,
    AgentRunLifecycle,
    AgentRunOriginKind,
    AgentRunOutcome,
)
from eylo.modules.agent_runs.service import (
    AgentRunWaitState,
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
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.pipelines.agent_run_tools import bind_agent_run_tool_command
from eylo.pipelines.agent_run_transcript import (
    AgentRunTranscript,
    AgentRunTranscriptBridge,
    AgentRunTranscriptError,
    PendingToolCallsModel,
    with_replay_messages,
)
from eylo.pipelines.agents import build_executable_agent_resolver
from eylo.pipelines.conversation.conversation_runner import ExistingConversationModel
from eylo.pipelines.conversation.domain import agent_spec_from_context
from eylo.pipelines.conversation.tool_executor import PlatformToolExecutor
from eylo.pipelines.sandbox.sessions import discard_live_run_sessions
from eylo.pipelines.system_tools.availability import (
    filter_available_system_tools,
    refresh_context_tool_availability,
)

if TYPE_CHECKING:
    from eylo.modules.agents.schemas.indb import AgentInDb
    from eylo.modules.tools.schemas.indb import ToolInDb

_HEARTBEAT_SECONDS = 120
_HEARTBEAT_INTERVAL_SECONDS = 30
_OBJECTIVE_RESULT_LIMIT_BYTES = 65_536
_COMPLETE_OBJECTIVE_TOOL = "complete_objective"
_REQUEST_OBJECTIVE_INPUT_TOOL = "request_objective_input"
_PAUSE_STATUSES = {
    RunStatus.WAITING_FOR_INPUT,
    RunStatus.WAITING_FOR_APPROVAL,
}
_CONTROL_INSTRUCTIONS = """\
Use the agent's published tools when they help achieve the objective. Sandbox
compute is optional and exists only when the published agent has sandbox tools.
If one identified user answer is genuinely required, call
`request_objective_input`. A normal final answer concludes the objective as
achieved. To return a structured result or conclude that the objective cannot
be achieved, call `complete_objective`. Never claim a tool action happened
unless its returned result says it happened.\
"""


class ObjectiveAgentRunInvalid(Exception):
    """An objective run no longer agrees with its immutable authority."""


class ObjectiveAgentRunExhausted(Exception):
    """The filed objective reached an explicit step or deadline boundary."""


class ObjectiveAgentRunRetryable(Exception):
    """A tool call is persisted but has no canonical result yet."""


@dataclass(slots=True)
class _ObjectiveExecutionContext:
    """In-memory adapter context; no synthetic conversation row is created."""

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


@dataclass(frozen=True, slots=True)
class ObjectiveFrameworkTurn:
    result: RunResult
    captured: dict[str, object]


class ObjectiveControlToolExecutor:
    """Own objective wait/terminal controls; delegate published product tools."""

    def __init__(self, delegate: ToolExecutor) -> None:
        self._delegate = delegate

    async def execute(self, context: RunContext, call: ToolCall) -> ToolResult:
        if call.name == _REQUEST_OBJECTIVE_INPUT_TOOL:
            prompt = _required_text(call.arguments, "prompt", max_chars=8_192)
            expected_schema = call.arguments.get("expected_response_schema") or {}
            if not isinstance(expected_schema, dict):
                raise ObjectiveAgentRunInvalid(
                    "Objective input response schema must be an object."
                )
            return ToolResult(
                tool_call_id=call.id,
                content="Objective paused pending identified user input.",
                metadata={
                    "input_request": {
                        "prompt": prompt,
                        "expected_input_schema": expected_schema,
                    }
                },
            )
        if call.name == _COMPLETE_OBJECTIVE_TOOL:
            outcome = call.arguments.get("outcome")
            if outcome not in {
                AgentRunOutcome.ACHIEVED.value,
                AgentRunOutcome.UNACHIEVABLE.value,
            }:
                raise ObjectiveAgentRunInvalid(
                    "Objective completion outcome must be achieved or unachievable."
                )
            reason = call.arguments.get("reason")
            if outcome == AgentRunOutcome.UNACHIEVABLE.value:
                reason = _required_text(call.arguments, "reason", max_chars=4_000)
            elif reason is not None and not isinstance(reason, str):
                raise ObjectiveAgentRunInvalid(
                    "Objective completion reason must be text."
                )
            payload = {
                "outcome": outcome,
                "result": call.arguments.get("result"),
                "reason": reason,
            }
            terminal_output = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=terminal_output,
                metadata={
                    "terminal_response": True,
                    "terminal_output": terminal_output,
                },
            )
        return await self._delegate.execute(context, call)


class ObjectiveFrameworkRunner:
    """Resolve the exact published agent and run its neutral framework loop."""

    def __init__(
        self,
        *,
        model_factory: Callable[[dict, RunConfig], Model] | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self._model_factory = model_factory
        delegate = tool_executor or PlatformToolExecutor()
        self._tool_executor = ObjectiveControlToolExecutor(delegate)

    async def run(
        self,
        *,
        claim: AgentRunExecutionClaim,
        workflow_context: AgentRunWorkflowContext,
        wait: AgentRunWaitState | None,
        max_steps: int,
        deadline: datetime,
    ) -> ObjectiveFrameworkTurn:
        execution_context = await _build_execution_context(claim)
        await refresh_context_tool_availability(
            execution_context,
            runtime_facts=(
                ToolRuntimeFact.DURABLE_EXECUTION,
                ToolRuntimeFact.AGENT_RUN,
            ),
        )
        published_agent = agent_spec_from_context(execution_context)
        control_tools = _objective_control_tools()
        published_names = {tool.name for tool in published_agent.tools}
        collisions = published_names & {tool.name for tool in control_tools}
        if collisions:
            raise ObjectiveAgentRunInvalid(
                "Published tool names collide with objective run controls."
            )
        agent = published_agent.model_copy(
            update={"tools": (*published_agent.tools, *control_tools)}
        )

        transcript = AgentRunTranscript(
            organization_id=claim.organization_id,
            agent_run_id=claim.run_id,
        )
        replay = await transcript.replay()
        remaining_steps = max_steps - len(replay.command_ids)
        remaining_seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
        if remaining_steps <= 0:
            raise ObjectiveAgentRunExhausted(
                f"Reached the explicit {max_steps}-tool-step limit."
            )
        if remaining_seconds <= 0:
            raise ObjectiveAgentRunExhausted(
                "Reached the explicit objective deadline."
            )

        config = RunConfig(
            max_turns=remaining_steps,
            request_timeout_seconds=remaining_seconds,
            stream=False,
            prompt_caching=getattr(settings, "ENABLE_PROMPT_CACHING", False),
        )
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
            run_context: RunContext,
            current_input: RunInput,
            response: ModelResponse,
            tool_calls: tuple[ToolCall, ...],
        ) -> None:
            captured["response"] = response
            captured["tool_calls"] = tool_calls
            await bridge.after_model_response(
                run_context,
                current_input,
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
        result = await FrameworkRunner(
            model,
            tool_executor=self._tool_executor,
        ).run(
            agent,
            run_input,
            config=config,
            local_context=local_context,
        )
        if result.status is RunStatus.FAILED:
            replay_after_failure = await transcript.replay()
            if replay_after_failure.pending_calls:
                raise ObjectiveAgentRunRetryable(
                    "Persisted objective tool call requires durable replay."
                )
        return ObjectiveFrameworkTurn(result=result, captured=captured)

    async def _resume_input(
        self,
        *,
        claim: AgentRunExecutionClaim,
        wait: AgentRunWaitState,
        run_input: RunInput,
        agent,
        execution_context: _ObjectiveExecutionContext,
        config: RunConfig,
        workflow_context: AgentRunWorkflowContext,
        transcript: AgentRunTranscript,
        command_ids: dict[str, UUID],
    ) -> RunInput:
        objective = wait.continuation.get("objective")
        if not isinstance(objective, dict):
            raise ObjectiveAgentRunInvalid(
                "Objective continuation is missing tool state."
            )
        try:
            call = ToolCall.model_validate(objective["tool_call"])
        except (KeyError, TypeError, ValueError) as error:
            raise ObjectiveAgentRunInvalid(
                "Objective continuation contains an invalid tool call."
            ) from error

        async def resolve_result() -> dict[str, Any]:
            if wait.kind is AgentInputRequestKind.APPROVAL:
                response = wait.response
                if not isinstance(response, dict):
                    raise ObjectiveAgentRunInvalid(
                        "Approval response must be an object."
                    )
                decision = response.get("decision")
                if decision == "reject":
                    result = ToolResult(
                        tool_call_id=call.id,
                        content="The user rejected this tool action.",
                        is_error=True,
                        metadata={"approval_rejected": True},
                    )
                elif decision == "approve":
                    command_id = command_ids.get(call.id)
                    if command_id is None:
                        raise ObjectiveAgentRunInvalid(
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
                    raise ObjectiveAgentRunInvalid(
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

        receipt = await workflow_context.step(
            key=f"resume:{wait.request_id}",
            version=1,
            operation=resolve_result,
        )
        if not isinstance(receipt, dict) or receipt.get("recorded") is not True:
            raise ObjectiveAgentRunInvalid("Objective resume receipt is invalid.")
        tool_result = await transcript.tool_result(call)
        if tool_result is None:
            raise ObjectiveAgentRunInvalid(
                "Objective resume result is unavailable."
            )
        return _append_resumed_tool_exchange(run_input, call, tool_result)


class ObjectiveAgentRunExecutor:
    """Execute a direct objective through its exact published agent revision."""

    def __init__(
        self,
        *,
        runner_factory: Callable[[], ObjectiveFrameworkRunner] | None = None,
    ) -> None:
        self._runner_factory = runner_factory or ObjectiveFrameworkRunner

    async def execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None:
        try:
            await self._execute(claim, context)
        except ObjectiveAgentRunExhausted as error:
            await _discard_compute(claim)
            await _finish_completed(
                claim,
                outcome=AgentRunOutcome.EXHAUSTED,
                result={"kind": "objective", "output": None},
                reason=str(error),
            )
        except (
            ObjectiveAgentRunInvalid,
            AgentRunTranscriptError,
            NotConfiguredError,
        ) as error:
            await _discard_compute(claim)
            await fail_agent_run(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
                failure_summary=_objective_failure_code(error),
            )
        except SandboxError:
            await _discard_compute(claim)
            await fail_agent_run(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
                failure_summary="sandbox_execution_failed",
            )

    async def _execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None:
        max_steps, deadline = _validate_claim(claim)
        wait = await load_agent_run_wait(
            organization_id=claim.organization_id,
            run_id=claim.run_id,
        )
        while True:
            if wait is not None:
                payload = await context.await_event(
                    event_name=wait.event_name,
                    key=wait.resume_step_key,
                    version=1,
                )
                _validate_resume_event(payload, claim=claim, wait=wait)

            turn_holder: list[ObjectiveFrameworkTurn] = []

            async def execute_turn() -> None:
                async with start_transaction() as db:
                    resumed_wait = None
                    if wait is not None:
                        resumed_wait = await resume_agent_run_in_transaction(
                            db,
                            organization_id=claim.organization_id,
                            run_id=claim.run_id,
                            request_id=wait.request_id,
                        )
                    turn = await self._runner_factory().run(
                        claim=claim,
                        workflow_context=context,
                        wait=resumed_wait,
                        max_steps=max_steps,
                        deadline=deadline,
                    )
                    await _persist_turn(claim=claim, turn=turn)
                    turn_holder.append(turn)

            await _run_with_heartbeat(context, execute_turn)
            turn = turn_holder[0]
            if turn.result.status not in _PAUSE_STATUSES:
                return
            wait = await load_agent_run_wait(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
            )
            if wait is None:
                raise ObjectiveAgentRunInvalid(
                    "Paused objective has no durable input request."
                )


async def _build_execution_context(
    claim: AgentRunExecutionClaim,
) -> _ObjectiveExecutionContext:
    resolved = await build_executable_agent_resolver(get_transaction()).resolve_exact(
        organization_id=claim.organization_id,
        agent_id=claim.agent_id,
        revision=claim.agent_revision,
        consumer_kind=TemplateConsumerKind.SANDBOX_AGENT,
    )
    conversation = SimpleNamespace(
        id=claim.run_id,
        organization_id=claim.organization_id,
        swarm_id=None,
        swarm_revision=None,
        channel=None,
        meta={},
    )
    return _ObjectiveExecutionContext(
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
    instructions = f"{execution_context.system_prompt}\n\n{_CONTROL_INSTRUCTIONS}"
    return RunInput(
        instructions=instructions,
        messages=(
            RunMessage(
                role="user",
                content=claim.goal,
                metadata={
                    "organization_id": str(claim.organization_id),
                    "agent_run_id": str(claim.run_id),
                    "request_id": str(claim.run_id),
                },
            ),
        ),
        tools=tools,
        metadata={
            "organization_id": str(claim.organization_id),
            "agent_run_id": str(claim.run_id),
            "request_id": str(claim.run_id),
        },
    )


def _objective_control_tools() -> tuple[ToolSpec, ToolSpec]:
    return (
        ToolSpec(
            name=_REQUEST_OBJECTIVE_INPUT_TOOL,
            description=(
                "Pause this objective indefinitely for one identified user answer."
            ),
            kind=ToolKind.SYSTEM,
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "minLength": 1},
                    "expected_response_schema": {"type": "object"},
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name=_COMPLETE_OBJECTIVE_TOOL,
            description=(
                "Conclude this objective with an achieved or unachievable outcome."
            ),
            kind=ToolKind.SYSTEM,
            input_schema={
                "type": "object",
                "properties": {
                    "outcome": {
                        "type": "string",
                        "enum": [
                            AgentRunOutcome.ACHIEVED.value,
                            AgentRunOutcome.UNACHIEVABLE.value,
                        ],
                    },
                    "result": {},
                    "reason": {"type": "string"},
                },
                "required": ["outcome"],
                "additionalProperties": False,
            },
        ),
    )


async def _persist_turn(
    *,
    claim: AgentRunExecutionClaim,
    turn: ObjectiveFrameworkTurn,
) -> None:
    result = turn.result
    if result.status in _PAUSE_STATUSES:
        await _discard_compute(claim)
        kind, prompt, expected_schema, continuation = _pause_fields(
            result,
            turn.captured,
        )
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

    lifecycle, outcome, projected, reason, failure = _terminal_fields(
        claim,
        result,
        turn.captured,
    )
    await _discard_compute(claim)
    await finish_agent_run_in_transaction(
        get_transaction(),
        organization_id=claim.organization_id,
        run_id=claim.run_id,
        lifecycle=lifecycle,
        outcome=outcome,
        result=projected,
        outcome_reason=reason,
        failure_summary=failure,
    )


def _pause_fields(
    result: RunResult,
    captured: dict[str, object],
) -> tuple[AgentInputRequestKind, str, dict, dict]:
    framework = result.metadata.get("continuation")
    if not isinstance(framework, dict):
        raise ObjectiveAgentRunInvalid(
            "Framework pause is missing continuation metadata."
        )
    calls = captured.get("tool_calls")
    if not isinstance(calls, tuple):
        raise ObjectiveAgentRunInvalid("Framework pause has no captured tool call.")
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
        raise ObjectiveAgentRunInvalid(
            "Framework pause continuation differs from its tool call."
        )

    if result.status is RunStatus.WAITING_FOR_APPROVAL:
        request = result.metadata.get("approval_request")
        if not isinstance(request, dict):
            raise ObjectiveAgentRunInvalid(
                "Approval pause is missing request metadata."
            )
        kind = AgentInputRequestKind.APPROVAL
        prompt = str(
            request.get("action_summary")
            or request.get("policy_reason")
            or "Approve this objective action?"
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
            raise ObjectiveAgentRunInvalid("Input pause is missing request metadata.")
        kind = AgentInputRequestKind.INPUT
        prompt = str(request.get("prompt") or "Provide the requested information.")
        expected_schema = request.get("expected_input_schema") or {}
        if not isinstance(expected_schema, dict):
            raise ObjectiveAgentRunInvalid(
                "Input response schema must be an object."
            )
    else:
        raise ObjectiveAgentRunInvalid("Framework result is not a pause.")

    return (
        kind,
        prompt,
        expected_schema,
        {
            "framework": framework,
            "request": request,
            "objective": {"tool_call": call.model_dump(mode="json")},
        },
    )


def _terminal_fields(
    claim: AgentRunExecutionClaim,
    result: RunResult,
    captured: dict[str, object],
) -> tuple[
    AgentRunLifecycle,
    AgentRunOutcome,
    dict | None,
    str | None,
    str | None,
]:
    if result.status is RunStatus.COMPLETED:
        outcome, output, reason = _objective_completion(result, captured)
        return (
            AgentRunLifecycle.COMPLETED,
            outcome,
            _objective_result(claim, result, output),
            reason,
            None,
        )
    if result.status in {RunStatus.TIMED_OUT, RunStatus.MAX_TURNS_EXCEEDED}:
        reason = f"Objective execution ended with {result.status.value}."
        return (
            AgentRunLifecycle.COMPLETED,
            AgentRunOutcome.EXHAUSTED,
            _objective_result(claim, result, None),
            reason,
            None,
        )
    return (
        AgentRunLifecycle.FAILED,
        AgentRunOutcome.FAILED,
        None,
        None,
        "objective_framework_failed",
    )


def _objective_completion(
    result: RunResult,
    captured: dict[str, object],
) -> tuple[AgentRunOutcome, object, str | None]:
    terminal_id = result.metadata.get("terminal_tool_call_id")
    calls = captured.get("tool_calls")
    if terminal_id is not None and isinstance(calls, tuple):
        call = next(
            (
                candidate
                for candidate in calls
                if isinstance(candidate, ToolCall)
                and candidate.id == terminal_id
                and candidate.name == _COMPLETE_OBJECTIVE_TOOL
            ),
            None,
        )
        if call is not None:
            outcome = AgentRunOutcome(str(call.arguments["outcome"]))
            reason = call.arguments.get("reason")
            return outcome, call.arguments.get("result"), reason
    return AgentRunOutcome.ACHIEVED, result.final_output, None


def _objective_result(
    claim: AgentRunExecutionClaim,
    result: RunResult,
    output: object,
) -> dict[str, Any]:
    projected = {
        "kind": "objective",
        "agent_run_id": str(claim.run_id),
        "framework_run_id": str(result.run_id),
        "framework_status": result.status.value,
        "output": output,
        "usage": result.usage.model_dump(mode="json"),
    }
    encoded = json.dumps(
        projected,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > _OBJECTIVE_RESULT_LIMIT_BYTES:
        raise ObjectiveAgentRunInvalid(
            "Objective result exceeds 65536 encoded bytes."
        )
    return projected


async def _finish_completed(
    claim: AgentRunExecutionClaim,
    *,
    outcome: AgentRunOutcome,
    result: dict,
    reason: str | None,
) -> None:
    projected = {**result, "agent_run_id": str(claim.run_id)}
    async with start_transaction() as db:
        await finish_agent_run_in_transaction(
            db,
            organization_id=claim.organization_id,
            run_id=claim.run_id,
            lifecycle=AgentRunLifecycle.COMPLETED,
            outcome=outcome,
            result=projected,
            outcome_reason=reason,
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
    return run_input.model_copy(
        update={
            "messages": (
                *run_input.messages,
                RunMessage(
                    role="assistant",
                    content=f"Tool call: {call.name}",
                    metadata={
                        "request_id": request_id,
                        "tool_call": call.model_dump(mode="json"),
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
        }
    )


def _validate_claim(claim: AgentRunExecutionClaim) -> tuple[int, datetime]:
    if (
        claim.origin_kind is not AgentRunOriginKind.OBJECTIVE
        or claim.origin_message_id is not None
        or claim.origin_schedule_run_id is not None
        or claim.context_manifest.get("kind") != "objective"
    ):
        raise ObjectiveAgentRunInvalid(
            "Objective executor received a different origin."
        )
    max_steps = claim.context_manifest.get("max_steps")
    deadline_value = claim.context_manifest.get("deadline")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int):
        raise ObjectiveAgentRunInvalid("Objective max_steps is invalid.")
    if not 1 <= max_steps <= 200 or not isinstance(deadline_value, str):
        raise ObjectiveAgentRunInvalid("Objective bounds are invalid.")
    try:
        deadline = datetime.fromisoformat(deadline_value)
    except ValueError as error:
        raise ObjectiveAgentRunInvalid("Objective deadline is invalid.") from error
    if deadline.tzinfo is None or deadline.utcoffset() is None:
        raise ObjectiveAgentRunInvalid("Objective deadline has no timezone.")
    return max_steps, deadline


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
        raise ObjectiveAgentRunInvalid(
            "Durable input event does not match the objective request."
        )


def _objective_failure_code(error: Exception) -> str:
    if isinstance(error, NotConfiguredError):
        return "objective_provider_not_configured"
    if isinstance(error, AgentRunTranscriptError):
        return "objective_transcript_invalid"
    return "objective_run_invalid"


def _required_text(
    source: dict,
    key: str,
    *,
    max_chars: int,
) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ObjectiveAgentRunInvalid(f"{key} must be text.")
    if len(value) > max_chars:
        raise ObjectiveAgentRunInvalid(f"{key} exceeds its character ceiling.")
    return value


async def _discard_compute(claim: AgentRunExecutionClaim) -> None:
    await discard_live_run_sessions(
        organization_id=claim.organization_id,
        agent_run_id=claim.run_id,
    )


async def _run_with_heartbeat(
    context: AgentRunWorkflowContext,
    operation: Callable[[], Awaitable[None]],
) -> None:
    task = asyncio.create_task(operation())
    try:
        while not task.done():
            remaining_milliseconds = await context.heartbeat(
                seconds=_HEARTBEAT_SECONDS
            )
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=min(
                        _HEARTBEAT_INTERVAL_SECONDS,
                        max(0.001, remaining_milliseconds / 1_000),
                    ),
                )
            except TimeoutError:
                continue
        await task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


__all__ = [
    "ObjectiveAgentRunExecutor",
    "ObjectiveAgentRunInvalid",
    "ObjectiveFrameworkRunner",
]
