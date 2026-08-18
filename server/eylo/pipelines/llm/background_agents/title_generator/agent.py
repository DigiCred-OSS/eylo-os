"""Title generation.

Generates a conversation title by invoking an LLM and updates the conversation
record, with fallbacks when LLM-based generation is not possible.

Runs as a background agent implementation, dispatched only where an operator
attached it. It used to be triggered by an event emitted on every user message;
that fan-out is gone.
"""

import logging
from typing import Optional

from eylo.common.database import start_transaction
from eylo.common.instrumentation import traced_agent
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.messages import MessageKind
from eylo.modules.conversations.services.conversations import (
    ConversationService,
)

from ..framework_prompt import resolve_background_agent
from .prompt import (
    build_title_generation_prompt,
)
from .utils import (
    call_llm_for_title_generation,
    ensure_title_max_length,
)

logger = logging.getLogger(__name__)


@traced_agent("title_generator")
async def process_title_generation_request(
    ctx: ConversationContext,
) -> bool:
    """Processes a request to generate a title for a given conversation.

    This involves fetching conversation data, invoking an LLM (with fallbacks),
    and updating the conversation record in the database.

    Returns True when a title was written, False when the work was unnecessary
    or could not be done. Background-agent dispatch maps that to COMPLETED or
    SKIPPED — under the todo-list model the thresholds below run at pickup, so
    a conversation that does not need a title produces a SKIPPED task rather
    than no task at all.
    """
    messages_ = ctx.filter_messages()
    if len(messages_) < 5 or ctx.conversation.has_triggered_title_generation:
        return False

    conversation_id = ctx.conversation.id
    logger.info(
        f"Processing title generation request for conversation {conversation_id}"
    )
    conversation = ctx.conversation

    # Pre-condition checks: Ensure conversation exists and title generation hasn't been attempted.
    if not conversation or conversation.has_triggered_title_generation:
        logger.info("Title generation already triggered or conversation not found.")
        return False

    if not conversation.id:
        logger.warning("Conversation ID is None. Aborting.")
        return False

    message_content = await _get_message_content_for_title_generation(ctx)
    if not ctx.primary_agent:
        logger.warning("Conversation %s has no primary agent", conversation_id)
        return False

    # --- LLM-based Title Generation Attempt --- #
    generated_title_from_llm = None
    if message_content:  # Only attempt LLM call if there's usable content.
        logger.debug(
            "Attempting LLM title generation for conversation %s",
            ctx.conversation.id,
        )
        try:
            # Build the prompts using the external utility function.
            system_prompt, llm_messages = build_title_generation_prompt(message_content)
            async with start_transaction(ro=True):
                resolved = await resolve_background_agent(
                    ctx.primary_agent,
                    generation_overrides={"max_tokens": 30, "temperature": 0.3},
                )

            # Call the helper function to interact with the LLM
            generated_title_from_llm = await call_llm_for_title_generation(
                system_prompt,
                llm_messages,
                ctx.primary_agent,
                resolved,
                ctx.conversation.id,
            )
            if generated_title_from_llm and generated_title_from_llm.strip():
                generated_title = generated_title_from_llm
            else:
                return False

            # Ensure the final title (whether from LLM or fallback) respects max DB length.
            generated_title = ensure_title_max_length(
                generated_title, str(ctx.conversation.id)
            )

            logger.info(
                "Updating generated title for conversation %s",
                ctx.conversation.id,
            )
            async with start_transaction():
                await ConversationService().update_title(
                    conversation_id=ctx.conversation.id,
                    title=generated_title,
                )
            return True
        except Exception as error:
            logger.error(
                "LLM title generation failed conversation=%s error_type=%s",
                ctx.conversation.id,
                type(error).__name__,
            )
            return False

    return False


async def _get_message_content_for_title_generation(
    ctx: ConversationContext,
) -> Optional[str]:
    """Extract message content for title generation.

    Uses the common get_text_content() method to extract text from all message types.
    """
    # Filter to only USER and ASSISTANT messages
    messages = ctx.filter_messages([MessageKind.USER, MessageKind.ASSISTANT])

    if not messages:
        return None

    message_lines = []
    for message in messages:
        # Use the common text extraction method
        text = message.get_text_content()

        if text:
            # Format as "role: content"
            message_lines.append(f"{message.kind.name}: {text}")

    if not message_lines:
        return None

    return "\n".join(message_lines)
