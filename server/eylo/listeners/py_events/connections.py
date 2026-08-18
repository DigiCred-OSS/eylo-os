"""Connection event listeners for WebSocket broadcasting."""

import logging

from eylo.events.schema.py_events.connections import (
    ConnectionExpiredEvent,
    ConnectionFailedEvent,
    ConnectionStartedEvent,
    ConnectionSuccessEvent,
)
from eylo.listeners.py_events.utils import broadcast_to_contact
from eylo.pipelines.websocket.schemas import WsEventAction

logger = logging.getLogger(__name__)


async def broadcast_connection_started(event: ConnectionStartedEvent):
    """Broadcast CONNECTION_STARTED event to the contact who initiated OAuth flow.

    This sends a WebSocket event to notify the widget that OAuth flow has begun.
    """
    logger.info(
        "[broadcast_connection_started] OAuth flow started for integration %s "
        "(contact=%s)",
        event.integration_id,
        event.contact_id,
    )

    await broadcast_to_contact(
        contact_id=event.contact_id,
        organization_id=event.organization_id,
        kind=WsEventAction.CONNECTION_STARTED,
        payload={
            "integration_id": str(event.integration_id),
            "vendor": event.vendor,
            "contact_id": str(event.contact_id),
        },
        event_name="CONNECTION_STARTED",
    )


async def broadcast_connection_success(event: ConnectionSuccessEvent):
    """Broadcast CONNECTION_SUCCESS event to the contact who completed OAuth flow.

    This sends a WebSocket event to notify the widget that connection succeeded.
    """
    logger.info(
        f"[broadcast_connection_success] Connection {event.connection_id} established "
        f"for {event.integration_name} (contact={event.contact_id})"
    )

    payload = {
        "connection_id": str(event.connection_id),
        "integration_id": str(event.integration_id),
        "integration_name": event.integration_name,
        "vendor": event.vendor,
    }

    await broadcast_to_contact(
        contact_id=event.contact_id,
        organization_id=event.organization_id,
        kind=WsEventAction.CONNECTION_SUCCESS,
        payload=payload,
        event_name="CONNECTION_SUCCESS",
    )


async def broadcast_connection_failed(event: ConnectionFailedEvent):
    """Broadcast CONNECTION_FAILED event to the contact whose OAuth flow failed.

    This sends a WebSocket event to notify the widget that connection failed.
    """
    logger.info(
        f"[broadcast_connection_failed] Connection failed for {event.integration_name} "
        f"(contact={event.contact_id}): {event.error}"
    )

    payload = {
        "error": event.error,
        "integration_id": str(event.integration_id),
        "integration_name": event.integration_name,
        "vendor": event.vendor,
    }

    await broadcast_to_contact(
        contact_id=event.contact_id,
        organization_id=event.organization_id,
        kind=WsEventAction.CONNECTION_FAILED,
        payload=payload,
        event_name="CONNECTION_FAILED",
    )


async def broadcast_connection_expired(event: ConnectionExpiredEvent):
    """Broadcast connection expired notification to the user.

    When token refresh is exhausted, emit AUTH_REQUIRED to show
    the reconnection panel in the widget UI.

    Args:
        event: ConnectionExpiredEvent with connection details

    """
    logger.info(
        f"Connection expired for connection_id={event.connection_id}, "
        f"reason={event.reason}. Broadcasting AUTH_REQUIRED to contact."
    )

    # Prepare AUTH_REQUIRED payload
    auth_required_payload = {
        "connection_id": str(event.connection_id),
        "integration_id": str(event.integration_id),
        "vendor": event.vendor,
        "integration_name": event.vendor,
        "reason": event.reason,
        "message": "Reconnect this service so the Agent can continue using it.",
        "action": "reconnect",
    }

    # Broadcast to the user who needs to reconnect (org-level connections have no contact)
    if not event.contact_id:
        logger.warning(
            "Cannot broadcast AUTH_REQUIRED for org-level connection %s — no contact_id",
            event.connection_id,
        )
        return

    await broadcast_to_contact(
        contact_id=event.contact_id,
        organization_id=event.organization_id,
        kind=WsEventAction.AUTH_REQUIRED,
        payload=auth_required_payload,
        event_name="AUTH_REQUIRED",
    )

    logger.info(
        f"AUTH_REQUIRED broadcast complete for connection_id={event.connection_id}"
    )
