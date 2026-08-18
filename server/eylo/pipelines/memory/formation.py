"""Queue what a conversation might have taught the durable memory pipeline.

Called from the run hooks of both paths — the framework bridge for text, the
platform `HookRunner` for voice — so neither has to know how memory forms.
Everything here is best-effort: memory is not worth failing a reply over.
"""

from __future__ import annotations

import logging

from eylo.modules.memory.scope import scope_from_context

logger = logging.getLogger(__name__)


async def enqueue_from_context(conversation_context, agent=None) -> bool:
    """Queue memory formation for this conversation. True when queued.

    Swallows everything. A memory not formed is a fact not learned; a reply
    that failed because memory could not be queued is an outage.
    """
    try:
        scope = scope_from_context(conversation_context, agent)
        if scope is None:
            return False

        selected_agent = agent or getattr(conversation_context, "primary_agent", None)
        config_id = getattr(selected_agent, "memory_provider_config_id", None)
        config_revision = getattr(
            selected_agent,
            "memory_provider_config_revision",
            None,
        )
        if config_id is None or config_revision is None:
            return False

        conversation = getattr(conversation_context, "conversation", None)
        if conversation is None:
            return False

        from eylo.pipelines.memory.durable_execution import enqueue_memory_formation

        await enqueue_memory_formation(
            scope=scope,
            memory_provider_config_id=config_id,
            memory_provider_config_revision=config_revision,
        )
        return True
    except Exception as error:  # noqa: BLE001 - never fail a run over memory
        logger.warning(
            "Could not queue memory formation: %s",
            type(error).__name__,
        )
        return False
