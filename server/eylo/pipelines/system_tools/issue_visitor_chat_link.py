"""Pipeline-backed system tool for issuing a one-time visitor chat link."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from eylo.modules.auth.schemas.widget_invitations import WidgetInvitationIssueRequest
from eylo.modules.auth.widget_invitations import WidgetInvitationIssuerKind
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.tools.services.executors.system_tools import logger
from eylo.pipelines.widget_invitations import issue_widget_invitation


async def issue_chat_link(
    visitor_email: str,
    visitor_name: str,
    initial_message: str,
    expires_in_minutes: int,
    *args: Any,
    ctx: Optional[ConversationContext] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Issue a one-time invitation; exchange creates the guest chat state."""
    del args, kwargs
    if not visitor_email:
        return {"success": False, "error": "A visitor email is required."}
    if not isinstance(expires_in_minutes, int) or not 1 <= expires_in_minutes <= 1440:
        return {
            "success": False,
            "error": "expires_in_minutes must be between 1 and 1440.",
        }
    if not ctx or not ctx.conversation or not ctx.primary_agent:
        return {"success": False, "error": "Conversation authority is unavailable."}
    agent_participant = ctx.get_primary_agent()
    if (
        agent_participant is None
        or agent_participant.agent_id is None
        or agent_participant.agent_revision is None
    ):
        return {
            "success": False,
            "error": "Primary agent has no exact published revision.",
        }
    organization_id: UUID | None = (
        getattr(
            ctx.primary_agent,
            "organization_id",
            None,
        )
        or ctx.conversation.organization_id
    )
    if organization_id is None:
        return {"success": False, "error": "Organization authority is unavailable."}

    try:
        issued = await issue_widget_invitation(
            organization_id=organization_id,
            request=WidgetInvitationIssueRequest(
                agent_id=agent_participant.agent_id,
                external_id=visitor_email,
                primary_email=visitor_email,
                name=visitor_name,
                opener=initial_message,
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=expires_in_minutes),
            ),
            issued_by_kind=WidgetInvitationIssuerKind.AGENT,
            issued_by_id=agent_participant.agent_id,
            pinned_agent_revision=agent_participant.agent_revision,
        )
    except Exception as error:  # noqa: BLE001 - tool returns one safe failure shape
        logger.error(
            "Guest-chat invitation issuance failed error_type=%s",
            type(error).__name__,
        )
        return {"success": False, "error": "Could not issue the chat invitation."}
    return {
        "success": True,
        "visitor_chat_link": issued.invitation_url,
        "expires_at": issued.invitation.expires_at.isoformat(),
        "warning_codes": list(issued.warning_codes),
    }


__all__ = ["issue_chat_link"]
