"""Small, explicit runner for the new framework execution path."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import AsyncIterator, TypeVar

from .agent import AgentSpec
from .approval import ApprovalActionKind, ApprovalRequest, RiskLevel
from .config import RunConfig
from .context import RunContext, RunInput, RunMessage
from .errors import GuardrailTripwireError
from .guardrail import Guardrail, GuardrailStage
from .hooks import RunHooks
from .items import RunItem, RunItemKind
from .model import Model, ModelBlockKind, ModelResponse, ModelUsage
from .result import RunResult, RunStatus
from .tool import ToolCall, ToolExecutionMode, ToolExecutor, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

T = TypeVar("T")
_MAX_APPROVAL_ARGUMENT_FIELDS = 32


@dataclass(frozen=True)
class ToolExecutionOutcome:
    """Tool execution batch plus optional interruption metadata."""

    results: tuple[ToolResult, ...]
    interrupted_status: RunStatus | None = None
    interruption_metadata: dict | None = None


async def _safe_hook(coro: Awaitable[None], hook_name: str) -> None:
    """Await a hook callback, logging but not propagating errors."""
    try:
        await coro
    except Exception as error:
        logger.error(
            "Hook failed hook=%s error_type=%s; preserving run result",
            hook_name,
            type(error).__name__,
        )


class FrameworkRunner:
    """Stateless orchestrator for one framework run.

    This mirrors the simplicity of ``openai-agents-python``: callers provide an
    agent, LLM-visible input, optional config/context, and get a ``RunResult``.
    The runner owns loop control only; persistence, durable scheduling, and
    transport remain outside this class.
    """

    def __init__(
        self,
        model: Model,
        *,
        tool_executor: ToolExecutor | None = None,
        hooks: RunHooks | None = None,
        guardrails: tuple[Guardrail, ...] = (),
    ) -> None:
        self._model = model
        self._tool_executor = tool_executor
        self._hooks = hooks or RunHooks()
        self._guardrails = guardrails

    async def run(
        self,
        agent: AgentSpec,
        run_input: RunInput,
        config: RunConfig | None = None,
        local_context: object | None = None,
    ) -> RunResult:
        """Run an agent to a terminal or interrupted state."""
        run_config = config or RunConfig()
        context = RunContext(
            config=run_config,
            current_agent=agent,
            handoff_chain=[agent],
            local_context=local_context,
        )
        items: list[RunItem] = []
        model_responses: list[ModelResponse] = []
        current_input = run_input

        await _safe_hook(self._hooks.on_run_start(context), "on_run_start")

        try:
            await self._check_input_guardrails(context, current_input)

            for turn in range(1, run_config.max_turns + 1):
                context.turn = turn

                if context.is_timed_out:
                    result = self._build_result(
                        context,
                        status=RunStatus.TIMED_OUT,
                        items=items,
                        model_responses=model_responses,
                        error_message="Run timed out.",
                    )
                    await _safe_hook(
                        self._hooks.on_run_end(context, result), "on_run_end"
                    )
                    return result

                await _safe_hook(
                    self._hooks.on_agent_start(context, context.current_agent),
                    "on_agent_start",
                )
                await _safe_hook(
                    self._hooks.on_llm_start(context, current_input), "on_llm_start"
                )

                response = await _await_with_timeout(
                    context,
                    self._model.generate(
                        current_input,
                        context.current_agent.model_settings,
                    ),
                )
                model_responses.append(response)
                context.usage = _add_usage(context.usage, response.usage)
                await _safe_hook(
                    self._hooks.on_llm_end(context, response), "on_llm_end"
                )

                text = _extract_text(response)
                tool_calls = _extract_tool_calls(response)

                if tool_calls:
                    await _apply_model_response_update(
                        context,
                        current_input,
                        response,
                        tool_calls,
                    )
                    if text:
                        items.append(
                            RunItem(
                                run_id=context.run_id,
                                kind=RunItemKind.MESSAGE,
                                message=text,
                                payload={"role": "assistant", "content": text},
                            )
                        )
                    tool_results = await self._execute_tools(
                        context,
                        _available_tool_specs(context, current_input),
                        tool_calls,
                        items,
                        response,
                    )
                    if tool_results.interrupted_status is not None:
                        result = self._build_result(
                            context,
                            status=tool_results.interrupted_status,
                            items=items,
                            model_responses=model_responses,
                            metadata=tool_results.interruption_metadata or {},
                        )
                        await _safe_hook(
                            self._hooks.on_run_end(context, result), "on_run_end"
                        )
                        return result
                    executed_tool_calls = tool_calls[: len(tool_results.results)]
                    current_input = _append_tool_messages(
                        current_input,
                        executed_tool_calls,
                        tool_results.results,
                        response,
                    )
                    current_input = await _apply_post_tool_update(
                        context,
                        current_input,
                        tool_results.results,
                    )
                    terminal_tool_result = _terminal_tool_result(tool_results.results)
                    terminal_output = _terminal_output_from_tool_result(
                        terminal_tool_result
                    )
                    if terminal_output is not None:
                        items.append(
                            RunItem(
                                run_id=context.run_id,
                                kind=RunItemKind.MESSAGE,
                                message=terminal_output,
                                payload={
                                    "role": "assistant",
                                    "content": terminal_output,
                                },
                            )
                        )
                        result = self._build_result(
                            context,
                            status=RunStatus.COMPLETED,
                            items=items,
                            model_responses=model_responses,
                            final_output=terminal_output,
                            metadata=_terminal_metadata_from_tool_result(
                                terminal_tool_result
                            ),
                        )
                        await self._check_output_guardrails(context, result)
                        await _safe_hook(
                            self._hooks.on_run_end(context, result), "on_run_end"
                        )
                        return result
                    continue

                if text:
                    item = RunItem(
                        run_id=context.run_id,
                        kind=RunItemKind.MESSAGE,
                        message=text,
                        payload={"role": "assistant", "content": text},
                    )
                    items.append(item)
                    result = self._build_result(
                        context,
                        status=RunStatus.COMPLETED,
                        items=items,
                        model_responses=model_responses,
                        final_output=text,
                    )
                    await self._check_output_guardrails(context, result)
                    await _safe_hook(
                        self._hooks.on_run_end(context, result), "on_run_end"
                    )
                    return result

                # Model returned neither text nor tool calls (empty/refusal).
                result = self._build_result(
                    context,
                    status=RunStatus.COMPLETED,
                    items=items,
                    model_responses=model_responses,
                    final_output=None,
                )
                await _safe_hook(self._hooks.on_run_end(context, result), "on_run_end")
                return result

            result = self._build_result(
                context,
                status=RunStatus.MAX_TURNS_EXCEEDED,
                items=items,
                model_responses=model_responses,
                error_message="Run exceeded max turns.",
            )
            await _safe_hook(self._hooks.on_run_end(context, result), "on_run_end")
            return result

        except TimeoutError:
            result = self._build_result(
                context,
                status=RunStatus.TIMED_OUT,
                items=items,
                model_responses=model_responses,
                error_message="Run timed out.",
            )
            await _safe_hook(self._hooks.on_run_end(context, result), "on_run_end")
            return result
        except Exception as error:
            await _safe_hook(self._hooks.on_error(context, error), "on_error")
            guardrail_blocked = isinstance(error, GuardrailTripwireError)
            status = (
                RunStatus.GUARDRAIL_TRIPPED if guardrail_blocked else RunStatus.FAILED
            )
            result = self._build_result(
                context,
                status=status,
                items=items,
                model_responses=model_responses,
                error_message=(
                    "A guardrail blocked the run."
                    if guardrail_blocked
                    else "Run failed."
                ),
                metadata={
                    "failure_code": (
                        "guardrail_blocked" if guardrail_blocked else "run_failed"
                    ),
                    "error_type": type(error).__name__,
                },
            )
            await _safe_hook(self._hooks.on_run_end(context, result), "on_run_end")
            return result

    async def run_streamed(
        self,
        agent: AgentSpec,
        run_input: RunInput,
        config: RunConfig | None = None,
        local_context: object | None = None,
    ) -> AsyncIterator[RunItem]:
        """Run an agent and stream framework items as they are produced."""
        result = await self.run(
            agent,
            run_input,
            config=config,
            local_context=local_context,
        )
        for item in result.items:
            yield item

    async def _execute_tools(
        self,
        context: RunContext,
        tool_specs: tuple[ToolSpec, ...],
        tool_calls: tuple[ToolCall, ...],
        items: list[RunItem],
        model_response: ModelResponse,
    ) -> ToolExecutionOutcome:
        """Execute model-requested tools."""
        results: list[ToolResult] = []
        tool_specs_by_name = {tool.name: tool for tool in tool_specs}
        for call in tool_calls:
            await self._check_tool_input_guardrails(context, call)
            items.append(
                RunItem(
                    run_id=context.run_id,
                    kind=RunItemKind.TOOL_CALL,
                    payload={
                        "id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                )
            )
            await _apply_tool_call_update(context, call, model_response)
            tool_spec = tool_specs_by_name.get(call.name)
            policy_result = _tool_policy_result(context, tool_spec, call)
            if policy_result is not None:
                if policy_result.interrupted_status is not None:
                    result = _pause_tool_result(
                        call,
                        policy_result.interrupted_status,
                        policy_result.interruption_metadata or {},
                    )
                    await self._record_tool_result(
                        context,
                        call,
                        result,
                        items,
                        emit_tool_end=False,
                    )
                    items.append(_approval_request_item(context, policy_result))
                    return _interrupted_tool_outcome(
                        results,
                        result,
                        policy_result.interrupted_status,
                        policy_result.interruption_metadata,
                    )

                assert policy_result.results
                result = policy_result.results[0]
                await self._record_tool_result(
                    context,
                    call,
                    result,
                    items,
                    emit_tool_end=False,
                )
                results.append(result)
                continue

            if self._tool_executor is None:
                raise ValueError(
                    "Model requested tools but no tool executor is configured."
                )

            await _safe_hook(self._hooks.on_tool_start(context, call), "on_tool_start")
            try:
                result = await _await_with_timeout(
                    context,
                    self._tool_executor.execute(context, call),
                )
            except Exception as error:
                result = ToolResult(
                    tool_call_id=call.id,
                    content="Error: Tool execution failed.",
                    is_error=True,
                    metadata={"tool_execution_failed": True},
                )
                await self._record_tool_result(
                    context,
                    call,
                    result,
                    items,
                    emit_tool_end=False,
                )
                raise error
            approval_metadata = _approval_metadata_from_tool_result(call, result)
            if approval_metadata is not None:
                await self._record_tool_result(
                    context,
                    call,
                    result,
                    items,
                    emit_tool_end=True,
                )
                items.append(_approval_request_item(context, approval_metadata))
                return _interrupted_tool_outcome(
                    results,
                    result,
                    RunStatus.WAITING_FOR_APPROVAL,
                    approval_metadata.interruption_metadata,
                )
            input_metadata = _input_metadata_from_tool_result(call, result)
            if input_metadata is not None:
                await self._record_tool_result(
                    context,
                    call,
                    result,
                    items,
                    emit_tool_end=True,
                )
                items.append(_input_request_item(context, input_metadata))
                return _interrupted_tool_outcome(
                    results,
                    result,
                    RunStatus.WAITING_FOR_INPUT,
                    input_metadata.interruption_metadata,
                )
            try:
                await self._check_tool_output_guardrails(context, result)
            except GuardrailTripwireError:
                result = ToolResult(
                    tool_call_id=call.id,
                    content="Error: Tool output blocked by guardrail.",
                    is_error=True,
                    metadata={"tool_output_blocked": True},
                )
                await self._record_tool_result(
                    context,
                    call,
                    result,
                    items,
                    emit_tool_end=False,
                )
                raise
            await self._record_tool_result(
                context,
                call,
                result,
                items,
                emit_tool_end=True,
            )
            results.append(result)
            if _terminal_output_from_tool_results((result,)) is not None:
                break

        return ToolExecutionOutcome(results=tuple(results))

    async def _record_tool_result(
        self,
        context: RunContext,
        call: ToolCall,
        result: ToolResult,
        items: list[RunItem],
        *,
        emit_tool_end: bool,
    ) -> None:
        """Persist and record a tool result, preserving hook ordering."""
        await _apply_tool_result_update(context, call, result)
        if emit_tool_end:
            await _safe_hook(
                self._hooks.on_tool_end(context, call, result),
                "on_tool_end",
            )
        items.append(_tool_result_item(context, result))

    async def _check_input_guardrails(
        self,
        context: RunContext,
        run_input: RunInput,
    ) -> None:
        for guardrail in self._guardrails:
            if guardrail.spec.stage != GuardrailStage.INPUT:
                continue
            result = await guardrail.check_input(context, run_input)
            if result.tripwire_triggered:
                raise GuardrailTripwireError(result.message or result.name)

    async def _check_output_guardrails(
        self,
        context: RunContext,
        result: RunResult,
    ) -> None:
        for guardrail in self._guardrails:
            if guardrail.spec.stage != GuardrailStage.OUTPUT:
                continue
            guardrail_result = await guardrail.check_output(context, result)
            if guardrail_result.tripwire_triggered:
                raise GuardrailTripwireError(
                    guardrail_result.message or guardrail_result.name
                )

    async def _check_tool_input_guardrails(
        self,
        context: RunContext,
        call: ToolCall,
    ) -> None:
        for guardrail in self._guardrails:
            if guardrail.spec.stage != GuardrailStage.TOOL_INPUT:
                continue
            result = await guardrail.check_tool_input(context, call)
            if result.tripwire_triggered:
                raise GuardrailTripwireError(result.message or result.name)

    async def _check_tool_output_guardrails(
        self,
        context: RunContext,
        tool_result: ToolResult,
    ) -> None:
        for guardrail in self._guardrails:
            if guardrail.spec.stage != GuardrailStage.TOOL_OUTPUT:
                continue
            result = await guardrail.check_tool_output(context, tool_result)
            if result.tripwire_triggered:
                raise GuardrailTripwireError(result.message or result.name)

    @staticmethod
    def _build_result(
        context: RunContext,
        *,
        status: RunStatus,
        items: list[RunItem],
        model_responses: list[ModelResponse],
        final_output: str | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> RunResult:
        return RunResult(
            run_id=context.run_id,
            status=status,
            final_output=final_output,
            items=tuple(items),
            model_responses=tuple(model_responses),
            usage=context.usage,
            starting_agent=context.handoff_chain[0] if context.handoff_chain else None,
            final_agent=context.current_agent,
            error_message=error_message,
            metadata=metadata or {},
        )


async def _await_with_timeout(
    context: RunContext,
    awaitable: Awaitable[T],
) -> T:
    """Await an operation without exceeding the run's remaining wall-clock timeout."""
    return await asyncio.wait_for(
        awaitable,
        timeout=context.remaining_timeout_seconds,
    )


def _extract_text(response: ModelResponse) -> str:
    """Return combined text blocks from a model response."""
    chunks: list[str] = []
    for block in response.blocks:
        if block.kind != ModelBlockKind.TEXT:
            continue
        if isinstance(block.content, str):
            chunks.append(block.content)
        elif isinstance(block.content, dict):
            text = block.content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _extract_tool_calls(response: ModelResponse) -> tuple[ToolCall, ...]:
    """Return tool calls requested by a model response."""
    calls: list[ToolCall] = []
    for block in response.blocks:
        if block.kind != ModelBlockKind.TOOL_CALL:
            continue
        if not isinstance(block.content, dict):
            raise ValueError("Tool call block content must be an object.")
        calls.append(ToolCall.model_validate(block.content))
    return tuple(calls)


def _append_tool_messages(
    run_input: RunInput,
    tool_calls: tuple[ToolCall, ...],
    tool_results: tuple[ToolResult, ...],
    model_response: ModelResponse,
) -> RunInput:
    """Return input with tool calls/results appended for the next turn."""
    messages = list(run_input.messages)
    request_id = run_input.metadata.get("request_id")
    model_meta = _model_response_metadata_for_next_turn(model_response)
    results_by_call_id = {result.tool_call_id: result for result in tool_results}
    calls_by_id = {call.id: call for call in tool_calls}

    for block in model_response.blocks:
        if block.kind == ModelBlockKind.TEXT:
            text = _extract_text(
                ModelResponse(
                    id=model_response.id,
                    model=model_response.model,
                    blocks=(block,),
                )
            )
            if text:
                messages.append(
                    RunMessage(
                        role="assistant",
                        content=text,
                        metadata={
                            "request_id": str(request_id) if request_id else None,
                            "meta": model_meta,
                        },
                    )
                )
            continue

        if block.kind != ModelBlockKind.TOOL_CALL:
            continue

        parsed_call = ToolCall.model_validate(block.content)
        result = results_by_call_id.get(parsed_call.id)
        if result is None:
            continue
        call = calls_by_id.get(parsed_call.id, parsed_call)
        messages.extend(
            (
                RunMessage(
                    role="assistant",
                    content=f"Tool call: {call.name}",
                    metadata={
                        "request_id": str(request_id) if request_id else None,
                        "meta": model_meta,
                        "tool_call": {
                            "id": call.id,
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                    },
                ),
                RunMessage(
                    role="tool",
                    content=_tool_result_content_for_message(result),
                    metadata={
                        "request_id": str(request_id) if request_id else None,
                        "meta": _tool_result_metadata_for_next_turn(result),
                        "tool_result": {
                            "tool_call_id": result.tool_call_id,
                            "name": call.name,
                            "is_error": result.is_error,
                            "content": result.content,
                        },
                    },
                ),
            )
        )

    return run_input.model_copy(
        update={
            "messages": tuple(messages),
            "metadata": run_input.metadata.model_copy(
                update={
                    "transient_tool_message_count": len(messages)
                    - len(run_input.messages)
                }
            ),
        }
    )


def _tool_result_content_for_message(result: ToolResult) -> str:
    """Serialize structured tool output for the model-visible message contract."""
    if isinstance(result.content, str):
        return result.content
    return json.dumps(
        result.content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _tool_result_metadata_for_next_turn(result: ToolResult) -> dict:
    """Return metadata safe to round-trip into transient tool-result messages."""
    return {
        "framework": True,
        "tool_call_id": result.tool_call_id,
        "is_error": result.is_error,
        "metadata": {
            key: value
            for key, value in result.metadata.model_dump(mode="json").items()
            if key not in {"terminal_output"}
        },
    }


def _model_response_metadata_for_next_turn(response: ModelResponse) -> dict:
    """Return model metadata in the shape existing LLM adapters understand."""
    response_data = response.model_dump()
    return {
        **response_data,
        "framework": True,
        "llm_response": response_data,
        "model_response": response_data,
    }


async def _apply_post_tool_update(
    context: RunContext,
    run_input: RunInput,
    tool_results: tuple[ToolResult, ...],
) -> RunInput:
    """Allow application adapters to refresh local context after tool side effects."""
    if not isinstance(context.local_context, dict):
        return run_input

    callback = context.local_context.get("after_tool_results")
    if callback is None:
        return run_input
    updated_input = await callback(context, run_input, tool_results)
    if not isinstance(updated_input, RunInput):
        raise TypeError("after_tool_results must return RunInput.")
    return updated_input


async def _apply_model_response_update(
    context: RunContext,
    run_input: RunInput,
    response: ModelResponse,
    tool_calls: tuple[ToolCall, ...],
) -> None:
    """Run application-local side effects for model responses with tools."""
    if not isinstance(context.local_context, dict):
        return

    callback = context.local_context.get("after_model_response")
    if callback is None:
        return
    await callback(context, run_input, response, tool_calls)


async def _apply_tool_result_update(
    context: RunContext,
    call: ToolCall,
    result: ToolResult,
) -> None:
    """Run application-local side effects for tool results."""
    if not isinstance(context.local_context, dict):
        return

    callback = context.local_context.get("after_tool_result")
    if callback is None:
        return
    await callback(context, call, result)


async def _apply_tool_call_update(
    context: RunContext,
    call: ToolCall,
    response: ModelResponse,
) -> None:
    """Run application-local side effects for a tool call before execution."""
    if not isinstance(context.local_context, dict):
        return

    callback = context.local_context.get("before_tool_call")
    if callback is None:
        return
    await callback(context, call, response)


def _tool_policy_result(
    context: RunContext,
    tool_spec: ToolSpec | None,
    call: ToolCall,
) -> ToolExecutionOutcome | None:
    """Return policy-driven outcome before dispatching a tool executor."""
    if tool_spec is None:
        result = ToolResult(
            tool_call_id=call.id,
            content="Error: The requested tool is not available to this agent.",
            is_error=True,
            metadata={"tool_policy_violation": True, "reason": "unknown_tool"},
        )
        return ToolExecutionOutcome(results=(result,))

    if tool_spec.execution_mode == ToolExecutionMode.DISABLED:
        result = ToolResult(
            tool_call_id=call.id,
            content="Error: Tool execution is disabled by policy.",
            is_error=True,
            metadata={
                "tool_policy_violation": True,
                "reason": "disabled_tool",
            },
        )
        return ToolExecutionOutcome(results=(result,))

    if tool_spec.execution_mode == ToolExecutionMode.REQUIRES_APPROVAL:
        approval_request = ApprovalRequest(
            durable_run_id=context.run_id,
            requested_by_agent_id=context.current_agent.id,
            action_kind=ApprovalActionKind.TOOL_CALL,
            action_summary=_tool_approval_summary(tool_spec),
            action_payload_redacted=_tool_approval_payload(tool_spec, call),
            risk_level=RiskLevel.MEDIUM,
            policy_reason="Stored tool policy requires approval before execution.",
        )
        return ToolExecutionOutcome(
            results=(),
            interrupted_status=RunStatus.WAITING_FOR_APPROVAL,
            interruption_metadata=_approval_interruption_metadata(
                call,
                approval_request.model_dump(mode="json"),
            ),
        )

    return None


def _tool_approval_summary(tool_spec: ToolSpec) -> str:
    """Describe the stored tool authority without reflecting model output."""
    slug = tool_spec.metadata.get("slug")
    tool_id = tool_spec.metadata.get("id")
    revision = tool_spec.metadata.get("revision")
    if isinstance(slug, str) and isinstance(tool_id, str) and isinstance(revision, int):
        return f"Approve tool action {slug} ({tool_id}@{revision})."
    return "Approve this tool action."


def _tool_approval_payload(tool_spec: ToolSpec, call: ToolCall) -> dict:
    """Project only stored identity and schema-owned argument structure."""
    payload: dict[str, object] = {}
    tool_id = tool_spec.metadata.get("id")
    revision = tool_spec.metadata.get("revision")
    if isinstance(tool_id, str):
        payload["tool_id"] = tool_id
    if isinstance(revision, int) and revision > 0:
        payload["tool_revision"] = revision

    properties = tool_spec.input_schema.get("properties")
    schema_fields = set(properties) if isinstance(properties, dict) else set()
    recognized_fields = sorted(
        field
        for field in call.arguments
        if isinstance(field, str) and field in schema_fields
    )
    payload["argument_fields"] = recognized_fields[:_MAX_APPROVAL_ARGUMENT_FIELDS]
    payload["argument_count"] = len(call.arguments)
    payload["unrecognized_argument_count"] = sum(
        field not in schema_fields for field in call.arguments
    )
    if len(recognized_fields) > _MAX_APPROVAL_ARGUMENT_FIELDS:
        payload["omitted_argument_field_count"] = (
            len(recognized_fields) - _MAX_APPROVAL_ARGUMENT_FIELDS
        )
    return payload


def _available_tool_specs(
    context: RunContext,
    run_input: RunInput,
) -> tuple[ToolSpec, ...]:
    """Return the model-visible tools for the current turn."""
    tools_by_name = {tool.name: tool for tool in context.current_agent.tools}
    tools_by_name.update({tool.name: tool for tool in run_input.tools})
    return tuple(tools_by_name.values())


def _approval_metadata_from_tool_result(
    call: ToolCall,
    result: ToolResult,
) -> ToolExecutionOutcome | None:
    """Return approval interruption when a tool executor reports one."""
    approval_request = result.metadata.get("approval_request")
    if not isinstance(approval_request, dict):
        return None

    return ToolExecutionOutcome(
        results=(),
        interrupted_status=RunStatus.WAITING_FOR_APPROVAL,
        interruption_metadata=_approval_interruption_metadata(
            call,
            approval_request,
        ),
    )


def _input_metadata_from_tool_result(
    call: ToolCall,
    result: ToolResult,
) -> ToolExecutionOutcome | None:
    """Return input-request interruption when a tool executor reports one."""
    input_request = result.metadata.get("input_request")
    if not isinstance(input_request, dict):
        return None

    return ToolExecutionOutcome(
        results=(),
        interrupted_status=RunStatus.WAITING_FOR_INPUT,
        interruption_metadata=_input_interruption_metadata(call, input_request),
    )


def _pause_tool_result(
    call: ToolCall,
    status: RunStatus,
    metadata: dict,
) -> ToolResult:
    """Create a paired tool result so persisted provider history stays valid."""
    if status == RunStatus.WAITING_FOR_APPROVAL:
        content = "Tool execution paused pending approval."
    else:
        content = "Tool execution paused pending user input."
    return ToolResult(
        tool_call_id=call.id,
        content=content,
        metadata={
            "tool_execution_paused": True,
            "status": status.value,
            **metadata,
        },
    )


def _interrupted_tool_outcome(
    prior_results: list[ToolResult],
    result: ToolResult,
    status: RunStatus,
    metadata: dict | None,
) -> ToolExecutionOutcome:
    return ToolExecutionOutcome(
        results=(*prior_results, result),
        interrupted_status=status,
        interruption_metadata=metadata,
    )


def _approval_interruption_metadata(
    call: ToolCall,
    approval_request: dict,
) -> dict:
    """Build continuation metadata for approval-gated tool calls."""
    return {
        "approval_request": approval_request,
        "continuation": {
            "type": "tool_approval",
            "tool_call_id": call.id,
        },
    }


def _input_interruption_metadata(
    call: ToolCall,
    input_request: dict,
) -> dict:
    """Build continuation metadata for input-gated tool calls."""
    return {
        "input_request": input_request,
        "continuation": {
            "type": "tool_input",
            "tool_call_id": call.id,
        },
    }


def _approval_request_item(
    context: RunContext,
    outcome: ToolExecutionOutcome,
) -> RunItem:
    """Represent a pause-for-approval as an inspectable run item."""
    return RunItem(
        run_id=context.run_id,
        kind=RunItemKind.APPROVAL_REQUEST,
        payload=outcome.interruption_metadata or {},
        message="Approval required before executing a tool action.",
    )


def _input_request_item(
    context: RunContext,
    outcome: ToolExecutionOutcome,
) -> RunItem:
    """Represent a pause-for-input as an inspectable run item."""
    return RunItem(
        run_id=context.run_id,
        kind=RunItemKind.INPUT_REQUEST,
        payload=outcome.interruption_metadata or {},
        message="Input required before completing a tool action.",
    )


def _tool_result_item(context: RunContext, result: ToolResult) -> RunItem:
    """Return the standard item shape for an observed tool result."""
    return RunItem(
        run_id=context.run_id,
        kind=RunItemKind.TOOL_RESULT,
        message=_tool_result_content_for_message(result),
        payload={
            "tool_call_id": result.tool_call_id,
            "content": result.content,
            "is_error": result.is_error,
        },
    )


def _terminal_output_from_tool_results(
    tool_results: tuple[ToolResult, ...],
) -> str | None:
    """Return terminal tool output when a tool intentionally ends the run."""
    return _terminal_output_from_tool_result(_terminal_tool_result(tool_results))


def _terminal_tool_result(
    tool_results: tuple[ToolResult, ...],
) -> ToolResult | None:
    return next(
        (result for result in tool_results if result.metadata.get("terminal_response")),
        None,
    )


def _terminal_output_from_tool_result(result: ToolResult | None) -> str | None:
    if result is None:
        return None
    output = result.metadata.get("terminal_output") or result.content
    return str(output)


def _terminal_metadata_from_tool_result(
    result: ToolResult | None,
) -> dict:
    """Return result metadata for terminal tool completions."""
    if result is None:
        return {}
    return {
        "terminal_response": True,
        "terminal_tool_call_id": result.tool_call_id,
    }


def _add_usage(current: ModelUsage, incoming: ModelUsage) -> ModelUsage:
    """Return accumulated usage without mutating frozen value objects."""
    return ModelUsage(
        input_tokens=current.input_tokens + incoming.input_tokens,
        output_tokens=current.output_tokens + incoming.output_tokens,
        cache_creation_input_tokens=(
            current.cache_creation_input_tokens + incoming.cache_creation_input_tokens
        ),
        cache_read_input_tokens=(
            current.cache_read_input_tokens + incoming.cache_read_input_tokens
        ),
        reasoning_tokens=current.reasoning_tokens + incoming.reasoning_tokens,
    )
