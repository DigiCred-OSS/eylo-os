"""Broadcast conversation lifecycle events to connected contacts."""

import logging

from eylo.common.database import start_transaction
from eylo.events.schema.py_events.base import ConversationCreatedEvent
from eylo.listeners.schema import ConversationUpdatedEvent
from eylo.modules.conversations.schemas.conversations import (
    ConversationApiResponseSchema,
)
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.pipelines.websocket.schemas import WsEventAction
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


async def broadcast_created_conversation(event: ConversationCreatedEvent):
    """Broadcast conversation:created to all contact participants.

    Without this, widget clients never learn about server-initiated
    conversations (e.g. campaign outreach) and their state stays stale.
    """
    async with start_transaction(ro=True):
        participants_indb = await ConversationParticipantService().list_by_conversation(
            conversation_id=event.conversation_id
        )
    contacts = ConversationParticipantService.filter_contact_participants(
        participants_indb
    )

    logger.info(
        "Broadcasting conversation:created to %d contacts for conversation %s",
        len(contacts),
        event.conversation_id,
    )

    payload = ConversationApiResponseSchema.model_validate(
        event.conversation
    ).model_dump(by_alias=True)

    for contact in contacts:
        await S_ws_manager.reply_to_conversation_contact(
            contact_id=contact.entity_id,
            organization_id=event.organization_id,
            conversation_id=event.conversation_id,
            kind=WsEventAction.CONVERSATION_CREATED,
            payload=payload,
        )


async def broadcast_updated_conversation(event: ConversationUpdatedEvent):
    async with start_transaction(ro=True):
        participants_indb = await ConversationParticipantService().list_by_conversation(
            conversation_id=event.conversation.id
        )
    contacts = ConversationParticipantService.filter_contact_participants(
        participants_indb
    )

    logger.info(f"Broadcasting conversation update to {len(contacts)} contacts")

    for contact in contacts:
        await S_ws_manager.reply_to_conversation_contact(
            contact_id=contact.entity_id,
            organization_id=event.conversation.organization_id,
            conversation_id=event.conversation.id,
            kind=WsEventAction.CONVERSATION_UPDATED,
            payload=ConversationApiResponseSchema.model_validate(
                event.conversation
            ).model_dump(by_alias=True),
        )
