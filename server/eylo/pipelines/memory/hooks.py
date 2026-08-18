"""Agent-run hook that enqueues post-run memory formation."""

from __future__ import annotations

import logging

from eylo.modules.agents.hooks.types import HookContext, RunHooks
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.pipelines.memory.formation import enqueue_from_context

logger = logging.getLogger(__name__)

# Below this the exchange is pleasantries. Extraction costs an LLM call, and
# running one on "thanks, bye" is paying to learn nothing.
MIN_MESSAGES_TO_LEARN = 2


class MemoryHooks(RunHooks):
    """Learn from a run, on the platform hook path used by the voice pipeline.

    Formation only. **Recall does not live here** — it happens where the system
    prompt is assembled, in `ConversationContextService`, because that is where
    the prompt slot is and both paths already go through it. A hook that
    mutated the prompt after it was built would silently do nothing.
    """

    async def on_agent_end(
        self, context: HookContext, agent: AgentInDb, output
    ) -> None:
        """Queue durable memory formation without extracting inside the hook."""
        messages = context.conversation_context.filter_messages()
        if len(messages) < MIN_MESSAGES_TO_LEARN:
            return
        await enqueue_from_context(context.conversation_context, agent)
