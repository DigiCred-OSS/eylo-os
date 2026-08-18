"""Member issuance and public one-time exchange for guest chat invitations."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from eylo.common.revisions import DefinitionRevisionError
from eylo.modules.agents.domain import InvalidAgentDefinitionError
from eylo.modules.agents.exceptions import AgentError, AgentNotFoundError
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.schemas.widget_invitations import (
    WidgetInvitationExchangeRequest,
    WidgetInvitationExchangeResponse,
    WidgetInvitationIssueRequest,
    WidgetInvitationIssueResponse,
)
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.auth.widget_invitations import (
    WidgetInvitationConfigurationError,
    WidgetInvitationInvalid,
    WidgetInvitationIssuerKind,
    WidgetInvitationUnavailable,
)
from eylo.modules.contacts.domain import ContactError, ContactIdentityInvalid
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.pipelines.widget_invitations import (
    exchange_widget_invitation,
    issue_widget_invitation,
)

private_router = APIRouter(
    prefix="/{organization_id}/widget-invitations",
    tags=["widget-invitations"],
)
public_router = APIRouter(
    prefix="/public/widget-invitations",
    tags=["widget-invitations"],
)


@private_router.post("", status_code=201, response_model=WidgetInvitationIssueResponse)
async def issue_invitation(
    organization_id: UUID,
    request: WidgetInvitationIssueRequest,
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> WidgetInvitationIssueResponse:
    try:
        issued = await issue_widget_invitation(
            organization_id=organization_id,
            request=request,
            issued_by_kind=WidgetInvitationIssuerKind.MEMBER,
            issued_by_id=current_user.member_id,
        )
    except AgentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Not found.") from error
    except ContactIdentityInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except WidgetInvitationInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (AgentError, DefinitionRevisionError, InvalidAgentDefinitionError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ContactError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except WidgetInvitationConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    invitation = issued.invitation
    return WidgetInvitationIssueResponse(
        invitation_id=invitation.id,
        contact_id=invitation.contact_id,
        agent_id=invitation.agent_id,
        agent_revision=invitation.agent_revision,
        expires_at=invitation.expires_at,
        invitation_url=issued.invitation_url,
        warning_codes=list(issued.warning_codes),
    )


@public_router.post(
    "/exchange",
    response_model=WidgetInvitationExchangeResponse,
)
async def exchange_invitation(
    payload: WidgetInvitationExchangeRequest,
    request: Request,
) -> WidgetInvitationExchangeResponse:
    user_agent = (request.headers.get("user-agent") or "")[:1024] or None
    ip_address = (request.client.host if request.client else "")[:64] or None
    try:
        exchanged = await exchange_widget_invitation(
            payload,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except (
        AgentError,
        ContactError,
        ConversationNotFound,
        DefinitionRevisionError,
        InvalidAgentDefinitionError,
        WidgetInvitationUnavailable,
    ) as error:
        raise HTTPException(status_code=404, detail="Not found.") from error
    return WidgetInvitationExchangeResponse(
        organization_id=exchanged.organization_id,
        contact_id=exchanged.contact_id,
        conversation_id=exchanged.conversation_id,
        session_token=exchanged.session_token,
        session_expires_at=exchanged.session_expires_at,
    )


__all__ = ["private_router", "public_router"]
