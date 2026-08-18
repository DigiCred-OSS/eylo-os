"""Authentication event listeners for WebSocket broadcasting."""

import logging

from eylo.events.schema.py_events.base import AuthRequiredEvent
from eylo.listeners.py_events.utils import broadcast_to_conversation_contact
from eylo.pipelines.websocket.schemas import WsEventAction

logger = logging.getLogger(__name__)


async def broadcast_auth_required(event: AuthRequiredEvent):
    """Broadcast AUTH_REQUIRED event to the contact who needs to authenticate.

    This sends a WebSocket event to the user's widget/client to show the
    connection panel and initiate OAuth flow.
    """
    logger.info(
        f"[broadcast_auth_required] Received event for {event.integration_name} "
        f"(conversation={event.conversation_id}, contact={event.contact_id})"
    )

    # Send to the specific contact who needs to authenticate
    if event.contact_id:
        payload = {
            "conversation_id": str(event.conversation_id),
            "integration_id": str(event.integration_id),
            "vendor": event.vendor,
            "auth_kind": event.auth_kind,
            "integration_name": event.integration_name,
            "reason": event.reason,
            "contact_id": str(event.contact_id) if event.contact_id else None,
            "message": event.message,
        }
        logger.info(
            f"[broadcast_auth_required] Sending to contact {event.contact_id}: {payload}"
        )

        await broadcast_to_conversation_contact(
            contact_id=event.contact_id,
            organization_id=event.organization_id,
            conversation_id=event.conversation_id,
            kind=WsEventAction.AUTH_REQUIRED,
            payload=payload,
            event_name=f"AUTH_REQUIRED for {event.integration_name}",
        )
    else:
        logger.warning(
            f"[broadcast_auth_required] No contact_id for AUTH_REQUIRED event in conversation {event.conversation_id}"
        )
