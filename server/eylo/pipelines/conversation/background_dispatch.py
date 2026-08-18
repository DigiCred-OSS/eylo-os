"""Dispatch enabled published background Agents after a conversation turn."""

from __future__ import annotations

import logging
from uuid import UUID

from eylo.common.revisions import DefinitionRef

logger = logging.getLogger(__name__)


async def dispatch_background_agents(
    *,
    agent_id: UUID,
    conversation_context,
    request_id: UUID | None,
) -> int:
    """Enqueue every enabled background agent attached to `agent_id`.

    Returns how many were dispatched, for the caller to log. Never raises: a
    background agent is supplementary by definition, so failing to dispatch one
    must not fail the run that triggered it. The framework already wraps hook
    calls, but relying on that alone would lose the reason in a generic
    "hook failed" line.
    """
    refs = await _published_background_refs(agent_id, conversation_context)
    if not refs:
        return 0

    from eylo.pipelines.parallel_agents.task_dispatcher import TaskDispatcher

    dispatcher = TaskDispatcher(conversation_context)
    instruction = (
        "A conversational run completed. Perform your configured work for "
        "this conversation."
    )

    dispatched = 0
    for ref in refs:
        # Per attachment: one background agent failing to enqueue must not
        # cost the others their dispatch.
        try:
            await dispatcher.dispatch_background_agent(
                background_agent_id=ref.definition_id,
                background_agent_revision=ref.revision,
                instruction=instruction,
                request_id=request_id,
            )
            dispatched += 1
        except Exception as error:
            logger.error(
                "Background agent=%s was not dispatched for agent=%s error_type=%s",
                ref.definition_id,
                agent_id,
                type(error).__name__,
            )
    return dispatched


async def _published_background_refs(
    agent_id: UUID,
    conversation_context,
) -> tuple[DefinitionRef, ...]:
    """Read the exact attachment snapshot filed with the running agent."""
    try:
        from eylo.modules.templates.domain import TemplateConsumerKind
        from eylo.pipelines.agents import build_executable_agent_resolver

        agent = conversation_context.primary_agent
        if agent is None or agent.published_revision is None:
            raise ValueError("Conversation agent revision is unavailable.")
        resolved = await build_executable_agent_resolver().resolve_exact(
            organization_id=conversation_context.conversation.organization_id,
            agent_id=agent_id,
            revision=agent.published_revision,
            consumer_kind=TemplateConsumerKind.CONVERSATIONAL_TEXT,
        )
        return resolved.background_agents
    except Exception as error:
        logger.error(
            "Could not read background agent attachments for agent=%s error_type=%s",
            agent_id,
            type(error).__name__,
        )
        return ()
