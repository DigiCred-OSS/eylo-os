"""Periodic tasks for conversation lifecycle management."""

import logging

from eylo.common.database import start_transaction
from eylo.modules.conversations.services.conversations import ConversationService

logger = logging.getLogger(__name__)


async def expire_old_conversations() -> dict:
    """Expire inactive conversations.

    Fact extraction used to happen here, once, when a conversation died. Memory
    now forms after every run through the run hooks, so nothing is learned or
    lost at expiry — see `modules/memory/hooks.py`.
    """
    logger.info("[ExpireOldConversationsTask] Starting expiration cycle")
    try:
        async with start_transaction() as db:
            expired = await ConversationService(db).expire_old_conversations()
        logger.info(
            f"[ExpireOldConversationsTask] Expired {len(expired)} conversations"
        )
        return {"expired_count": len(expired)}
    # The NotConfiguredError re-raise that used to sit here existed for fact
    # extraction, which needed an LLM. Expiring a conversation needs no
    # provider, so there is nothing left to propagate.
    except Exception as error:
        logger.error(
            "[ExpireOldConversationsTask] Failed error_type=%s",
            type(error).__name__,
        )
        return {"status": "error", "error": "Conversation expiration failed."}
