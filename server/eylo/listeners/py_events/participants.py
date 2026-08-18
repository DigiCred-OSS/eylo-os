"""Broadcast participant lifecycle events to connected contacts."""

import logging

from eylo.common.database import start_transaction
from eylo.events.schema.py_events.base import ParticipantCreatedEvent
from eylo.modules.conversations.schemas.participants import ParticipantApiResponseSchema
from eylo.modules.conversations.services.conversations import ConversationBaseService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.pipelines.websocket.schemas import WsEventAction
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


async def handle_participant_created(event: ParticipantCreatedEvent):
    """Broadcast participant created event to all participants in the conversation.

    This ensures real-time updates when new participants (e.g., agents during handoff) are added.
    """
    async with start_transaction(ro=True):
        participant_indb = event.participant
        if participant_indb is None:
            logger.warning(
                f"ParticipantCreatedEvent received without participant data: {event}"
            )
            return

        # Get conversation to access organization_id
        conversation_indb = await ConversationBaseService().get_(event.conversation_id)
        if conversation_indb is None:
            logger.error(
                f"Could not find conversation {event.conversation_id} for participant event"
            )
            return

        # Get all participants in the conversation to broadcast to
        participants_indb = await ConversationParticipantService().list_by_conversation(
            conversation_id=event.conversation_id
        )
        contacts = ConversationParticipantService.filter_contact_participants(
            participants_indb
        )

        logger.debug(
            f"Broadcasting participant created to {len(contacts)} contacts in conversation {event.conversation_id}"
        )

        # Broadcast to all contacts in the conversation
        for contact in contacts:
            await S_ws_manager.reply_to_conversation_contact(
                contact_id=contact.entity_id,
                organization_id=conversation_indb.organization_id,
                conversation_id=event.conversation_id,
                kind=WsEventAction.PARTICIPANT_CREATED,
                payload=ParticipantApiResponseSchema.model_validate(
                    participant_indb
                ).model_dump(by_alias=True),
            )

        logger.info(
            f"Participant {participant_indb.id} created and broadcast for conversation {event.conversation_id}"
        )
