"""File parallel task messages and their durable AgentRuns from composition."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import arrow

from eylo.common.database import get_transaction
from eylo.modules.agent_runs.absurd import spawn_agent_run
from eylo.modules.agent_runs.domain import (
    InitiatingPrincipalKind,
    InitiatingPrincipalRef,
)
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.message_content import SystemMessageContent
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageKind,
    RequestStatus,
)
from eylo.modules.conversations.services.messages import (
    MessageAgentRunFiling,
    MessageService,
)
from eylo.modules.parallel_agents.schemas import (
    SpawnTaskFnfResult,
    TaskContent,
)

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """Create SYSTEM/TASK messages and bind them to Absurd-owned AgentRuns.

    Called by the spawn_task_fnf system tool. Each call creates one TASK
    message and one AgentRun, then returns after the durable spawn attempt.
    """

    def __init__(self, ctx: ConversationContext):
        self.ctx = ctx
        self.message_service = MessageService()

    async def dispatch(
        self,
        instruction: str,
        swarm_id: str | None,
        request_id: UUID | None,
    ) -> SpawnTaskFnfResult:
        """Create a TASK message and spawn its durable AgentRun.

        Args:
            instruction: Self-contained task description.
            swarm_id: Target member slug, or None for a bare LLM task.
            request_id: Current request ID for tracing.

        Returns:
            Structured result with task_id and status.

        """
        swarm_agent = self._find_swarm_agent(swarm_id)
        if swarm_id is not None and swarm_agent is None:
            return SpawnTaskFnfResult(
                task_id="",
                status="error",
                instruction=instruction,
                swarm_id=swarm_id,
                error=f"Agent '{swarm_id}' not found in swarm",
            )

        agent_participant = self.ctx.get_primary_agent()
        primary_agent = self.ctx.primary_agent
        if (
            agent_participant is None
            or agent_participant.agent_id is None
            or agent_participant.agent_revision is None
            or primary_agent is None
        ):
            return SpawnTaskFnfResult(
                task_id="",
                status="error",
                instruction=instruction,
                swarm_id=swarm_id,
                error="No primary agent participant found",
            )

        resolved_swarm_agent = None
        resolved_topology = None
        if swarm_agent is not None:
            from eylo.modules.templates.domain import TemplateConsumerKind
            from eylo.pipelines.agents import build_executable_swarm_resolver

            if (
                self.ctx.conversation.swarm_id is None
                or self.ctx.conversation.swarm_revision is None
            ):
                return SpawnTaskFnfResult(
                    task_id="",
                    status="error",
                    instruction=instruction,
                    swarm_id=swarm_id,
                    error="Conversation has no pinned swarm topology",
                )
            resolved_topology = await build_executable_swarm_resolver().resolve_exact(
                organization_id=self.ctx.conversation.organization_id,
                swarm_id=self.ctx.conversation.swarm_id,
                revision=self.ctx.conversation.swarm_revision,
                consumer_kind=TemplateConsumerKind.SWARM_AGENT,
            )
            member = resolved_topology.member_by_slug(swarm_id)
            if (
                member is None
                or member.executable_agent.ref.definition_id != swarm_agent.id
            ):
                return SpawnTaskFnfResult(
                    task_id="",
                    status="error",
                    instruction=instruction,
                    swarm_id=swarm_id,
                    error=f"Agent '{swarm_id}' is not authorized by the pinned topology",
                )
            resolved_swarm_agent = member.executable_agent

        task_content = TaskContent(
            instruction=instruction,
            source_agent_id=agent_participant.agent_id,
            source_agent_revision=agent_participant.agent_revision,
            swarm_id=swarm_id,
            swarm_agent_id=(
                None
                if resolved_swarm_agent is None
                else resolved_swarm_agent.ref.definition_id
            ),
            swarm_agent_revision=(
                None
                if resolved_swarm_agent is None
                else resolved_swarm_agent.ref.revision
            ),
            swarm_topology_id=(
                None
                if resolved_topology is None
                else resolved_topology.ref.definition_id
            ),
            swarm_topology_revision=(
                None if resolved_topology is None else resolved_topology.ref.revision
            ),
            llm_provider_config_id=primary_agent.llm_provider_config_id,
            llm_provider_config_revision=primary_agent.llm_provider_config_revision,
        )

        filing = await self._file_task(
            task_content=task_content,
            sender_participant_id=agent_participant.id,
            request_id=request_id,
            task_type="swarm_agent" if swarm_id else "llm_task",
            meta={"task_type": "swarm_agent" if swarm_id else "llm_task"},
            idempotency_key=f"parallel-task:{uuid4()}",
        )

        await get_transaction().commit()

        try:
            await spawn_agent_run(
                organization_id=self.ctx.conversation.organization_id,
                run_id=filing.run_id,
            )
        except Exception as error:
            logger.error(
                "Parallel AgentRun=%s remains queued after spawn error_type=%s",
                filing.run_id,
                type(error).__name__,
            )

        logger.info(
            "Filed parallel task: msg=%s run=%s swarm=%s",
            filing.message.id,
            filing.run_id,
            swarm_id,
        )

        return SpawnTaskFnfResult(
            task_id=str(filing.message.id),
            status="dispatched",
            instruction=instruction,
            swarm_id=swarm_id,
        )

    async def dispatch_background_agent(
        self,
        *,
        background_agent_id: UUID,
        background_agent_revision: int,
        instruction: str,
        request_id: UUID | None,
    ) -> UUID | None:
        """Persist a TASK for an attached background agent and spawn its run.

        The same substrate as `dispatch`, triggered by attachment instead of by
        the model calling a tool. Returns the task message id, or None if the
        task could not even be persisted.

        The DB transaction commits before spawn. A process death between those
        steps leaves a queued AgentRun for the periodic outbox sweep. Nothing
        here calls an LLM or the network.
        """
        agent_participant = self.ctx.get_primary_agent()
        if (
            agent_participant is None
            or agent_participant.agent_id is None
            or agent_participant.agent_revision is None
        ):
            logger.warning(
                "No primary agent participant; cannot dispatch background "
                "agent %s for conversation %s",
                background_agent_id,
                self.ctx.conversation.id,
            )
            return None

        task_content = TaskContent(
            instruction=instruction,
            source_agent_id=agent_participant.agent_id,
            source_agent_revision=agent_participant.agent_revision,
            swarm_id=None,
            background_agent_id=background_agent_id,
            background_agent_revision=background_agent_revision,
        )

        filing_identity = request_id or uuid4()
        filing = await self._file_task(
            task_content=task_content,
            sender_participant_id=agent_participant.id,
            request_id=request_id,
            task_type="background_agent",
            meta={
                "task_type": "background_agent",
                "background_agent_id": str(background_agent_id),
                "background_agent_revision": background_agent_revision,
            },
            idempotency_key=(
                f"parallel-background:{self.ctx.conversation.id}:"
                f"{filing_identity}:{background_agent_id}:"
                f"{background_agent_revision}"
            ),
        )

        await get_transaction().commit()

        try:
            await spawn_agent_run(
                organization_id=self.ctx.conversation.organization_id,
                run_id=filing.run_id,
            )
        except Exception as error:
            logger.error(
                "Background AgentRun=%s remains queued after spawn error_type=%s",
                filing.run_id,
                type(error).__name__,
            )

        logger.info(
            "Filed background agent %s: msg=%s run=%s",
            background_agent_id,
            filing.message.id,
            filing.run_id,
        )
        return filing.message.id

    async def _file_task(
        self,
        *,
        task_content: TaskContent,
        sender_participant_id: UUID,
        request_id: UUID | None,
        task_type: str,
        meta: dict,
        idempotency_key: str,
    ) -> MessageAgentRunFiling:
        """File one task message and AgentRun in the caller transaction."""
        execution_agent_id, execution_agent_revision = (
            task_content.execution_agent_ref()
        )
        message = MessageCreate(
            conversation_id=self.ctx.conversation.id,
            sender_participant_id=sender_participant_id,
            created_at=arrow.utcnow().datetime,
            kind=MessageKind.SYSTEM,
            content_kind=MessageContentKind.TASK,
            content=SystemMessageContent(content=task_content.to_json()),
            request_id=request_id,
            request_status=RequestStatus.PENDING,
            meta=meta,
        )
        return await self.message_service.create_task_with_agent_run(
            message=message,
            principal=InitiatingPrincipalRef(
                organization_id=self.ctx.conversation.organization_id,
                kind=InitiatingPrincipalKind.WORKER,
                principal_id=task_content.source_agent_id,
            ),
            agent_id=execution_agent_id,
            agent_revision=execution_agent_revision,
            context_manifest={
                "kind": "parallel_task",
                "conversation_id": str(self.ctx.conversation.id),
                "task_type": task_type,
                "source_agent_id": str(task_content.source_agent_id),
                "source_agent_revision": task_content.source_agent_revision,
            },
            idempotency_key=idempotency_key,
        )

    def _find_swarm_agent(self, swarm_id: str | None) -> AgentInDb | None:
        """Return the selected configured swarm agent, if present."""
        if swarm_id is None:
            return None
        for agent in self.ctx.handoff_agents or []:
            if agent.slug == swarm_id:
                return agent
        return None
