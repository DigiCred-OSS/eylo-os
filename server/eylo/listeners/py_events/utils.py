"""Common utility functions for py_events listeners."""

import logging
from typing import Any, Dict
from uuid import UUID

from eylo.pipelines.websocket.schemas import WsEventAction
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


async def broadcast_to_conversation_contacts(
    *,
    contact_ids: tuple[UUID, ...],
    organization_id: UUID,
    conversation_id: UUID,
    kind: WsEventAction,
    payload: Dict[str, Any],
    event_name: str | None = None,
) -> None:
    """Broadcast one bounded lifecycle projection to explicit contacts."""
    if event_name:
        logger.debug(
            "Broadcasting %s to %d contacts in conversation %s",
            event_name,
            len(contact_ids),
            conversation_id,
        )

    for contact_id in contact_ids:
        await S_ws_manager.reply_to_conversation_contact(
            contact_id=contact_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            kind=kind,
            payload=payload,
        )

    if event_name:
        logger.info("%s event broadcast for conversation %s", event_name, conversation_id)


async def broadcast_to_contact(
    contact_id: UUID,
    organization_id: UUID,
    kind: WsEventAction,
    payload: Dict[str, Any],
    event_name: str | None = None,
) -> None:
    """Broadcast WebSocket event to a specific contact.

    Simplified utility for single-contact broadcasts like AUTH_REQUIRED.

    Args:
        contact_id: UUID of the contact to send to
        organization_id: UUID of the organization
        kind: WebSocket event action type
        payload: Event payload to broadcast
        event_name: Optional human-readable event name for logging

    """
    if event_name:
        logger.debug(f"Broadcasting {event_name} to contact {contact_id}")

    await S_ws_manager.reply_to_contact(
        contact_id=contact_id,
        organization_id=organization_id,
        kind=kind,
        payload=payload,
    )

    if event_name:
        logger.info(f"{event_name} event sent to contact {contact_id}")


async def broadcast_to_conversation_contact(
    *,
    contact_id: UUID,
    organization_id: UUID,
    conversation_id: UUID,
    kind: WsEventAction,
    payload: Dict[str, Any],
    event_name: str | None = None,
) -> None:
    """Broadcast one delta only to the contact's session for this chat."""
    if event_name:
        logger.debug(
            "Broadcasting %s to contact %s in conversation %s",
            event_name,
            contact_id,
            conversation_id,
        )
    await S_ws_manager.reply_to_conversation_contact(
        contact_id=contact_id,
        organization_id=organization_id,
        conversation_id=conversation_id,
        kind=kind,
        payload=payload,
    )
