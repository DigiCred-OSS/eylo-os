"""Run a published background Agent within its parent durable Agent run."""

from __future__ import annotations

import logging
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.llm_configs.wiring import build_llm_config_resolver
from eylo.modules.parallel_agents.schemas import TaskContent, WorkerResult
from eylo.pipelines.outbound.durable_execution import DurableStepContext

logger = logging.getLogger(__name__)


def background_run_config(stored_config=None):
    """A `RunConfig` for a background run. `max_handoffs` is always 0, forced.

    Budget is **not** per-agent configurable today. An earlier version read a
    `run_config` attribute off the agent's `llm_overrides`, which has six
    fields and no such attribute — so it always fell back to defaults while the
    docstring claimed otherwise. Nothing on the agent record can express a run
    budget yet; adding one is a schema change, not a lookup.

    `stored_config` is honoured when a caller passes one explicitly, which is
    what lets tests prove the handoff override wins over stored configuration.
    """
    from eylo.framework.agents.config import RunConfig

    base = stored_config if stored_config is not None else RunConfig()
    return base.model_copy(update={"max_handoffs": 0})


class BackgroundAgentWorker:
    """Executes one dispatched background agent task."""

    def __init__(
        self,
        task_content: TaskContent,
        organization_id: UUID,
        conversation_id: UUID,
        task_message_id: UUID,
        agent_run_id: UUID,
        durable_context: DurableStepContext,
    ) -> None:
        self.task_content = task_content
        self.organization_id = organization_id
        self.conversation_id = conversation_id
        self.task_message_id = task_message_id
        self.agent_run_id = agent_run_id
        self.durable_context = durable_context

    async def run(self) -> WorkerResult:
        from eylo.modules.agents.implementations import BACKGROUND_IMPLEMENTATIONS
        from eylo.modules.templates.domain import TemplateConsumerKind
        from eylo.pipelines.agents import build_executable_agent_resolver

        agent_id = self.task_content.background_agent_id
        agent_revision = self.task_content.background_agent_revision
        if agent_id is None or agent_revision is None:
            raise ValueError("Background task lacks an exact agent revision.")
        async with start_transaction(ro=True):
            resolved = await build_executable_agent_resolver().resolve_exact(
                organization_id=self.organization_id,
                agent_id=agent_id,
                revision=agent_revision,
                consumer_kind=TemplateConsumerKind.BACKGROUND_AGENT,
            )
        agent = resolved.agent

        if agent.implementation:
            # First-party code, which owns its own side effect and decides for
            # itself whether the work is still needed.
            implementation = BACKGROUND_IMPLEMENTATIONS.get(agent.implementation)
            if implementation is None:
                # Registered at write time, gone by dispatch time — a removed
                # or renamed built-in. Recorded, not silently skipped.
                raise ValueError(
                    f"Background agent {agent_id} names implementation "
                    f"{agent.implementation!r}, which is not registered."
                )
            return await self._run_implementation(agent)

        return await self._run_prompt_agent(resolved)

    async def _run_implementation(self, agent) -> WorkerResult:
        """Hand off to first-party code, which owns its own side effect.

        The implementation decides whether the work was needed — it is the only
        thing that can, since the threshold is its own business rule. `False`
        means it looked and found nothing to do, which is `SKIPPED` rather than
        a failure: the dispatcher never deduplicates, so redundant tasks are an
        expected outcome, not an error.
        """
        from eylo.pipelines.conversation.background_implementations import (
            run_implementation,
        )

        context = await self._conversation_context()
        did_work = await run_implementation(agent.implementation, context)

        return WorkerResult(
            text="" if did_work else "No work required.",
            model_used=agent.implementation,
            iterations_used=1,
            outcome="completed" if did_work else "skipped",
        )

    async def _run_prompt_agent(self, resolved) -> WorkerResult:
        """Run a prompt-only background agent and return its text.

        No side effect beyond the `TASK_RESULT` message the caller writes —
        that is the whole of what a tenant-created background agent may do.
        """
        from eylo.framework.agents.runner import FrameworkRunner

        agent = resolved.agent
        context = await self._conversation_context()
        context.primary_agent = agent
        context.tools = list(resolved.tools)
        context.handoff_agents = []
        context.handoff_agent_tools = {}
        context.system_prompt = resolved.system_prompt or ""
        run_config = background_run_config()
        spec = self._agent_spec(resolved)

        from eylo.pipelines.agent_run_transcript import (
            AgentRunTranscript,
            AgentRunTranscriptBridge,
            PendingToolCallsModel,
            with_replay_messages,
        )
        from eylo.pipelines.conversation.tool_executor import (
            PlatformToolExecutor,
        )

        async with start_transaction() as session:
            transcript = AgentRunTranscript(
                organization_id=self.organization_id,
                agent_run_id=self.agent_run_id,
            )
            replay = await transcript.replay()
            local_context = {
                "conversation_context": context,
                "agent_run_id": self.agent_run_id,
                "durable_context": self.durable_context,
                "tool_use_messages": {},
            }
            bridge = AgentRunTranscriptBridge(
                transcript=transcript,
                local_context=local_context,
                command_ids=replay.command_ids,
            )
            local_context.update(
                {
                    "after_model_response": bridge.after_model_response,
                    "before_tool_call": bridge.before_tool_call,
                    "after_tool_result": bridge.after_tool_result,
                }
            )
            model = PendingToolCallsModel(
                self._build_model(local_context, session),
                agent_run_id=self.agent_run_id,
                pending_calls=replay.pending_calls,
            )
            runner = FrameworkRunner(
                model,
                tool_executor=PlatformToolExecutor(),
            )
            result = await runner.run(
                spec,
                with_replay_messages(
                    self._build_run_input(resolved, context, spec),
                    replay,
                ),
                config=run_config,
                local_context=local_context,
            )
        from eylo.framework.agents.result import RunStatus

        if result.status is not RunStatus.COMPLETED:
            summary = (
                result.error_message or "Background framework run did not complete."
            )
            raise RuntimeError(f"{result.status.value}: {summary}")

        return WorkerResult(
            text=_result_text(result),
            model_used=_model_of(result, spec),
            iterations_used=len(result.model_responses or ()),
            outcome="completed",
        )

    async def _conversation_context(self):
        """The conversation as the built-ins already expect to receive it.

        Built the same way the live path builds it, so an implementation sees
        no difference between running under dispatch and running under the old
        fan-out — which is what makes the pre-migration behaviour the oracle.
        """
        from eylo.modules.conversations.services.conversations import (
            ConversationService,
        )
        from eylo.pipelines.conversation.context import (
            ConversationContextService,
        )

        async with start_transaction(ro=True):
            conversation = await ConversationService().get_(self.conversation_id)
            return await ConversationContextService().build(conversation)

    @staticmethod
    def _agent_spec(resolved):
        """An `AgentSpec` with handoffs forced empty.

        Not `handoffs=context.handoff_agents` filtered, and not a default —
        the tuple is empty unconditionally, so no stored configuration and no
        future caller can reintroduce chaining.
        """
        from eylo.pipelines.conversation.domain import (
            agent_spec_from_indb,
            tool_spec_from_indb,
        )

        tools = tuple(tool_spec_from_indb(tool) for tool in resolved.tools)
        return agent_spec_from_indb(resolved.agent, tools=tools, handoffs=())

    def _build_run_input(self, resolved, context, spec):
        """LLM-visible input for a prompt-only background run."""
        from eylo.framework.agents.context import RunInput, RunMessage
        from eylo.pipelines.conversation.domain import run_message_from_indb

        history = tuple(
            run_message_from_indb(message) for message in context.get_messages()
        )

        return RunInput(
            instructions=resolved.system_prompt or spec.instructions,
            messages=history
            + (
                RunMessage(
                    role="user",
                    content=self.task_content.instruction,
                    metadata={"request_id": str(self.task_message_id)},
                ),
            ),
            tools=spec.tools,
            metadata={
                "conversation_id": str(self.conversation_id),
                "request_id": str(self.task_message_id),
            },
        )

    def _build_model(self, context, db):
        """The vendor adapter. Raises NotConfiguredError if none resolves."""
        from eylo.pipelines.conversation.conversation_runner import (
            ExistingConversationModel,
        )

        return ExistingConversationModel(
            context,
            llm_resolver=build_llm_config_resolver(db),
        )


def _result_text(result) -> str:
    """The last text the model produced.

    Reads `block.content`, not `block.text` — an earlier version used the
    latter, which `ModelOutputBlock` does not have, so every prompt-only run
    would have reported empty output even once it stopped raising. Only TEXT
    blocks qualify: a tool-use block's content is a JSON object, not a reply.
    """
    from eylo.framework.agents.model import ModelBlockKind

    for response in reversed(result.model_responses or ()):
        for block in response.blocks or ():
            if block.kind is ModelBlockKind.TEXT and isinstance(block.content, str):
                return block.content
    return ""


def _model_of(result, spec) -> str:
    if result.model_responses:
        return result.model_responses[-1].model
    return spec.model_settings.model or "unknown"
