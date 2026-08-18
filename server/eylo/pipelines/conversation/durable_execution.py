"""Durable AgentRun executor for one message-backed conversation turn."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from eylo.common.config import settings
from eylo.common.database import start_transaction
from eylo.framework.agents import RunConfig as FrameworkRunConfig
from eylo.framework.agents.result import RunStatus
from eylo.modules.agent_runs.domain import AgentRunOriginKind
from eylo.modules.agent_runs.service import (
    AgentRunWaitState,
    load_agent_run_wait,
    resume_agent_run_in_transaction,
)
from eylo.modules.agent_runs.workflow import (
    AgentRunExecutionClaim,
    AgentRunWorkflowContext,
)
from eylo.modules.conversations.repositories.messages import (
    MessageAgentRunRepository,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageInDb,
    MessageKind,
)
from eylo.pipelines.parallel_agents import ParallelTaskAgentRunExecutor

from .conversation_runner import FrameworkConversationRunner
from .run_failure import fail_agent_run_and_converge_message

_HEARTBEAT_SECONDS = 120
_HEARTBEAT_INTERVAL_SECONDS = 30


class ConversationAgentRunInvalid(Exception):
    """A message-backed run no longer has valid immutable input."""


class ConversationAgentRunExecutor:
    """Reload IDs, execute the framework loop, persist one canonical result."""

    def __init__(
        self,
        *,
        runner_factory: Callable[[], FrameworkConversationRunner] | None = None,
        parallel_executor: ParallelTaskAgentRunExecutor | None = None,
    ) -> None:
        self._runner_factory = runner_factory or FrameworkConversationRunner
        self._parallel_executor = parallel_executor or ParallelTaskAgentRunExecutor()

    async def execute(
        self,
        claim: AgentRunExecutionClaim,
        context: AgentRunWorkflowContext,
    ) -> None:
        try:
            origin = await _load_origin_message(claim)
        except ConversationAgentRunInvalid:
            await fail_agent_run_and_converge_message(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
                failure_summary="message_agent_run_invalid",
            )
            return

        if (
            origin.kind == MessageKind.SYSTEM
            and origin.content_kind == MessageContentKind.TASK
        ):
            await self._parallel_executor.execute_origin(claim, context, origin)
            return
        if origin.kind != MessageKind.USER:
            await fail_agent_run_and_converge_message(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
                failure_summary="Message AgentRun origin is not executable.",
            )
            return

        config = FrameworkRunConfig(
            stream=getattr(settings, "ENABLE_LLM_STREAMING", False),
            prompt_caching=getattr(settings, "ENABLE_PROMPT_CACHING", False),
        )
        wait = await load_agent_run_wait(
            organization_id=claim.organization_id,
            run_id=claim.run_id,
        )
        while True:
            result_holder: list = []
            resumed_wait = None

            if wait is not None:
                event_payload = await context.await_event(
                    event_name=wait.event_name,
                    key=wait.resume_step_key,
                    version=1,
                )
                _validate_resume_event(event_payload, claim=claim, wait=wait)
                async with start_transaction() as session:
                    resumed_wait = await resume_agent_run_in_transaction(
                        session,
                        organization_id=claim.organization_id,
                        run_id=claim.run_id,
                        request_id=wait.request_id,
                    )

            async def run_turn() -> None:
                async with start_transaction():
                    runner = self._runner_factory()
                    if wait is None:
                        result = await runner.run(
                            conversation_id=origin.conversation_id,
                            user_message=origin,
                            config=config,
                            agent_run_id=claim.run_id,
                            expected_agent_id=claim.agent_id,
                            expected_agent_revision=claim.agent_revision,
                            durable_context=context,
                        )
                    else:
                        if resumed_wait is None:
                            raise ConversationAgentRunInvalid(
                                "Answered wait was not resumed before execution."
                            )
                        result = await runner.resume(
                            conversation_id=origin.conversation_id,
                            user_message=origin,
                            wait=resumed_wait,
                            config=config,
                            agent_run_id=claim.run_id,
                            expected_agent_id=claim.agent_id,
                            expected_agent_revision=claim.agent_revision,
                            durable_context=context,
                        )
                    result_holder.append(result)

            await _run_with_heartbeat(context, run_turn)
            result = result_holder[0]
            if result.status not in {
                RunStatus.WAITING_FOR_INPUT,
                RunStatus.WAITING_FOR_APPROVAL,
            }:
                return
            wait = await load_agent_run_wait(
                organization_id=claim.organization_id,
                run_id=claim.run_id,
            )
            if wait is None:
                raise ConversationAgentRunInvalid(
                    "Paused conversation has no durable input request."
                )


async def _load_origin_message(claim: AgentRunExecutionClaim) -> MessageInDb:
    if (
        claim.origin_kind is not AgentRunOriginKind.MESSAGE
        or claim.origin_message_id is None
    ):
        raise ConversationAgentRunInvalid(
            "Conversation execution requires a message origin."
        )

    async with start_transaction(ro=True) as session:
        origin = await MessageAgentRunRepository(session).get_origin_message(
            organization_id=claim.organization_id,
            message_id=claim.origin_message_id,
        )
        if origin is None:
            raise ConversationAgentRunInvalid(
                "The AgentRun origin message is unavailable."
            )
        message = MessageInDb.model_validate(origin)

    expected_conversation_id = claim.context_manifest.get("conversation_id")
    if expected_conversation_id != str(message.conversation_id):
        raise ConversationAgentRunInvalid(
            "The AgentRun context no longer matches its origin conversation."
        )
    return message


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
        raise ConversationAgentRunInvalid(
            "Durable input event does not match the identified request."
        )


async def _run_with_heartbeat(
    context: AgentRunWorkflowContext,
    operation: Callable[[], Awaitable[None]],
) -> None:
    """Keep the Absurd claim live; cancellation propagates through heartbeat."""
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


__all__ = ["ConversationAgentRunExecutor"]
