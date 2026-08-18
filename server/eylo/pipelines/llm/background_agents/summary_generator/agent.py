"""Context Management Background Agent.

This agent monitors conversation token usage and proactively manages context
by summarizing old messages when approaching token limits. It runs in the
background and does not impact user-facing latency.

Trigger logic (see utils.should_trigger_context_management):
- **Token trigger**: token usage ≥ 70 % of model context window.
- **Group trigger**: ≥ 20 request groups since the last SYSTEM SUMMARY.
  A "request group" is the set of messages sharing the same request_id
  (one user turn + agent response + tool calls).
"""

import logging
from dataclasses import dataclass

import arrow

from eylo.common.context_compaction import (
    CONTEXT_COMPACTION_META_KEY,
    compaction_meta,
    latest_context_compaction,
    ordered_messages,
    uncompacted_messages,
)
from eylo.common.database import start_transaction
from eylo.common.instrumentation import traced_agent
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.message_content import SystemMessageContent
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageInDb,
    MessageKind,
)
from eylo.modules.conversations.services.messages import MessageService

from ..framework_prompt import resolve_background_agent
from .utils import (
    count_conversation_tokens,
    flatten_groups,
    get_max_tokens_for_model,
    group_messages_by_request,
    should_trigger_context_management,
    summarize_messages_with_llm,
)

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TOKEN_THRESHOLD = 0.7  # Trigger at 70 % of max tokens
DEFAULT_GROUP_THRESHOLD = 20  # Trigger every 20 request groups
DEFAULT_RECENT_GROUPS = 5  # Preserve complete recent turns verbatim


@dataclass(frozen=True, slots=True)
class _CompactionSelection:
    messages: tuple[MessageInDb, ...]
    through: MessageInDb
    previous_summary: MessageInDb | None


@traced_agent("summary_generator")
async def process_context_management_request(
    ctx: ConversationContext,
) -> bool:
    """Process context management request.

    Returns True when a summary was written, False when the conversation was
    below threshold or the work could not be done — background-agent dispatch
    maps that to COMPLETED or SKIPPED.

    Flow:
    1. Count tokens in the conversation.
    2. Decide whether to trigger (token threshold or group threshold).
    3. Keep five complete recent groups and select the older uncompacted range.
    4. Generate a cumulative summary from the prior summary plus that range.
    5. Persist a SYSTEM / SUMMARY message with an exact compaction cursor.
    """
    conversation = ctx.conversation
    messages = ctx.messages or []

    logger.debug(f"Processing context management for conversation {conversation.id}")

    if not messages:
        return False

    # --- Resolve model info ---
    agent = ctx.primary_agent
    if not agent:
        logger.error(f"No agent for conversation {conversation.id}. Skipping.")
        return False

    try:
        async with start_transaction(ro=True):
            resolved = await resolve_background_agent(
                agent,
                generation_overrides={"max_tokens": 2000, "temperature": 0.3},
            )
    except Exception as error:
        logger.error(
            "Could not resolve summary LLM conversation=%s error_type=%s",
            conversation.id,
            type(error).__name__,
        )
        return False

    model = resolved.generation.model
    max_tokens = get_max_tokens_for_model(model)
    current_tokens = await count_conversation_tokens(ctx, resolved)

    logger.info(
        f"Conversation {conversation.id}: {current_tokens}/{max_tokens} tokens "
        f"({current_tokens / max_tokens * 100:.1f}%)"
    )

    # --- Should we manage context? ---
    should_manage, reason = should_trigger_context_management(
        current_tokens=current_tokens,
        max_tokens=max_tokens,
        tokens_threshold=DEFAULT_TOKEN_THRESHOLD,
        messages=uncompacted_messages(messages),
        group_threshold=DEFAULT_GROUP_THRESHOLD,
    )

    if not should_manage:
        logger.info(
            f"Context management not needed for {conversation.id}. "
            f"Below thresholds (tokens={DEFAULT_TOKEN_THRESHOLD * 100}%, "
            f"groups={DEFAULT_GROUP_THRESHOLD})"
        )
        return False

    logger.info(
        f"Context management triggered ({reason}) for {conversation.id}. "
        f"Token usage: {current_tokens / max_tokens * 100:.1f}%"
    )

    # --- Determine messages to summarize ---
    selection = _select_messages_to_summarize(messages, reason)

    if selection is None:
        logger.info(f"No messages to summarize for {conversation.id}. Skipping.")
        return False

    logger.info(
        f"Summarizing {len(selection.messages)} messages for {conversation.id} "
        f"(reason={reason})"
    )

    # --- Generate summary ---
    try:
        summary = await summarize_messages_with_llm(
            messages=list(selection.messages),
            conversation_id=conversation.id,
            agent=agent,
            resolved=resolved,
            prior_summary=(
                None
                if selection.previous_summary is None
                else selection.previous_summary.get_text_content()
            ),
        )
        if not summary:
            logger.warning(
                f"Failed to generate summary for {conversation.id}. Aborting."
            )
            return False

        logger.info("Generated summary for conversation %s", conversation.id)

    except Exception as error:
        logger.error(
            "Generating summary failed conversation=%s error_type=%s",
            conversation.id,
            type(error).__name__,
        )
        return False

    # --- Persist SYSTEM SUMMARY message ---
    async with start_transaction():
        await _create_context_summary_message(
            ctx,
            summary=summary,
            original_token_count=current_tokens,
            selection=selection,
        )

    logger.info(f"Context management completed for {conversation.id}.")
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _select_messages_to_summarize(
    messages: list[MessageInDb],
    reason: str,
) -> _CompactionSelection | None:
    """Return the subset of messages that should be fed to the summarizer.

    Both triggers keep complete recent request groups. A new summary is
    cumulative: it includes the previous summary plus only the newly compacted
    range, then advances an exact persisted message cursor.
    """
    if reason not in {"tokens", "groups"}:
        logger.error(f"Unknown trigger reason '{reason}'. Aborting.")
        return None
    groups = group_messages_by_request(uncompacted_messages(messages))
    if len(groups) <= DEFAULT_RECENT_GROUPS:
        logger.info(
            "Not enough complete request groups to compact (%s <= %s).",
            len(groups),
            DEFAULT_RECENT_GROUPS,
        )
        return None
    selected = ordered_messages(flatten_groups(groups[:-DEFAULT_RECENT_GROUPS]))
    if not selected:
        return None
    compaction = latest_context_compaction(messages)
    return _CompactionSelection(
        messages=tuple(selected),
        through=selected[-1],
        previous_summary=None if compaction is None else compaction.summary,
    )


async def _create_context_summary_message(
    ctx: ConversationContext,
    summary: str,
    original_token_count: int,
    selection: _CompactionSelection,
) -> MessageInDb:
    """Create a SYSTEM message containing context summary metadata.

    Args:
        conversation_id: Conversation ID
        summary: LLM-generated summary of old messages
        keep_recent_messages: Number of recent messages to keep
        original_token_count: Token count before summarization

    Returns:
        Created message

    """
    conversation_id = ctx.conversation.id
    contact_participant_id = ctx.get_primary_contact().id

    payload = SystemMessageContent(content=summary)

    # Create message using MessageCreate schema
    message_create = MessageCreate(
        conversation_id=conversation_id,
        sender_participant_id=contact_participant_id,
        created_at=arrow.utcnow().datetime,
        kind=MessageKind.SYSTEM,
        content_kind=MessageContentKind.SUMMARY,
        content=payload,
        request_id=None,  # System messages don't have request IDs
        meta={
            "original_token_count": original_token_count,
            CONTEXT_COMPACTION_META_KEY: compaction_meta(
                through=selection.through,
                source_message_count=len(selection.messages),
                previous_summary_id=(
                    None
                    if selection.previous_summary is None
                    else selection.previous_summary.id
                ),
            ),
        },
    )

    message = await MessageService().create_(message_create)

    logger.info(
        f"Created context summary SYSTEM message {message.id} for conversation {conversation_id}"
    )

    return message
