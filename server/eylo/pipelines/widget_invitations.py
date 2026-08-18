"""Compose auth, contact, agent, and conversation boundaries for guest chat."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
from uuid import UUID

from eylo.common.config import settings
from eylo.common.database import start_transaction
from eylo.modules.auth.models import AuthSessionModel, WidgetInvitationModel
from eylo.modules.auth.schemas.widget_invitations import (
    WidgetInvitationExchangeRequest,
    WidgetInvitationIssueRequest,
)
from eylo.modules.auth.services.session_service import AuthSessionService
from eylo.modules.auth.widget_invitations import (
    WidgetInvitationConfigurationError,
    WidgetInvitationIssuerKind,
    WidgetInvitationService,
    WidgetInvitationUnavailable,
)
from eylo.modules.contacts.schemas.indb import ContactCreateSchema, ContactRef
from eylo.modules.contacts.service import ContactService
from eylo.modules.conversations.models.conversations import ConversationChannels
from eylo.modules.conversations.schemas.conversations import (
    ConversationInitialMessage,
    ConversationInitialMessageContent,
    ConversationParticipant,
    ConversationStartRequest,
)
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.templates.domain import TemplateConsumerKind
from eylo.pipelines.agents import build_executable_agent_resolver


@dataclass(frozen=True, slots=True)
class IssuedWidgetInvitation:
    invitation: WidgetInvitationModel
    invitation_url: str
    warning_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExchangedWidgetInvitation:
    organization_id: UUID
    contact_id: UUID
    conversation_id: UUID
    session_token: str
    session_expires_at: datetime


async def issue_widget_invitation(
    *,
    organization_id: UUID,
    request: WidgetInvitationIssueRequest,
    issued_by_kind: WidgetInvitationIssuerKind,
    issued_by_id: UUID,
    pinned_agent_revision: int | None = None,
) -> IssuedWidgetInvitation:
    """Issue one opaque invitation without creating a guest session yet."""
    now = datetime.now(timezone.utc)
    async with start_transaction() as db:
        resolver = build_executable_agent_resolver(db)
        if pinned_agent_revision is None:
            resolved_agent = await resolver.resolve_for_new_work(
                organization_id=organization_id,
                agent_id=request.agent_id,
                consumer_kind=TemplateConsumerKind.CONVERSATIONAL_TEXT,
            )
        else:
            resolved_agent = await resolver.resolve_exact(
                organization_id=organization_id,
                agent_id=request.agent_id,
                revision=pinned_agent_revision,
                consumer_kind=TemplateConsumerKind.CONVERSATIONAL_TEXT,
            )

        resolution = await AuthSessionService(db).resolve_or_create_contact(
            ContactCreateSchema(
                organization_id=organization_id,
                external_id=request.external_id,
                primary_email=request.primary_email,
                primary_phone=request.primary_phone,
                name=request.name,
            )
        )
        if resolution.contact is None:
            raise WidgetInvitationUnavailable

        invitation, token = await WidgetInvitationService(db).issue(
            organization_id=organization_id,
            contact_id=resolution.contact.id,
            agent_id=resolved_agent.ref.definition_id,
            agent_revision=resolved_agent.ref.revision,
            opener=request.opener,
            expires_at=request.expires_at,
            issued_by_kind=issued_by_kind,
            issued_by_id=issued_by_id,
            now=now,
        )
        invitation_url = _build_invitation_url(token)
        return IssuedWidgetInvitation(
            invitation=invitation,
            invitation_url=invitation_url,
            warning_codes=resolution.warning_codes,
        )


async def exchange_widget_invitation(
    request: WidgetInvitationExchangeRequest,
    *,
    user_agent: str | None,
    ip_address: str | None,
) -> ExchangedWidgetInvitation:
    """Atomically consume an invitation into one session/conversation/opener."""
    now = datetime.now(timezone.utc)
    async with start_transaction() as db:
        invitations = WidgetInvitationService(db)
        invitation = await invitations.lock_for_exchange(request.token)
        if invitation.consumed_at is not None:
            if invitation.consumed_request_id != request.request_id:
                raise WidgetInvitationUnavailable
            return await _load_existing_exchange(invitation, now=now, db=db)
        if invitation.expires_at <= now:
            raise WidgetInvitationUnavailable

        contact = await ContactService(db).get_by_ref(
            ContactRef(
                organization_id=invitation.organization_id,
                contact_id=invitation.contact_id,
            )
        )
        if contact is None:
            raise WidgetInvitationUnavailable
        resolved_agent = await build_executable_agent_resolver(db).resolve_exact(
            organization_id=invitation.organization_id,
            agent_id=invitation.agent_id,
            revision=invitation.agent_revision,
            consumer_kind=TemplateConsumerKind.CONVERSATIONAL_TEXT,
        )
        session = await AuthSessionService(db).create_session_for_contact(
            contact=contact,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        conversation = await ConversationService(db).start_conversation(
            invitation.organization_id,
            ConversationStartRequest(
                **{
                    "from": ConversationParticipant(
                        kind=ParticipantKind.AGENT,
                        id=invitation.agent_id,
                    ),
                    "to": ConversationParticipant(
                        kind=ParticipantKind.CONTACT,
                        id=invitation.contact_id,
                    ),
                    "message": ConversationInitialMessage(
                        content=[
                            ConversationInitialMessageContent(
                                type="text",
                                text=invitation.opener,
                            )
                        ]
                    ),
                    "channel": ConversationChannels.WEB,
                    "context": {
                        "widget_invitation": {
                            "invitation_id": str(invitation.id),
                            "agent_id": str(invitation.agent_id),
                            "agent_revision": invitation.agent_revision,
                            "issued_by_kind": invitation.issued_by_kind,
                            "issued_by_id": str(invitation.issued_by_id),
                        }
                    },
                }
            ),
            resolved_agent=resolved_agent,
        )
        await invitations.record_consumed(
            invitation,
            request_id=request.request_id,
            session_id=session.id,
            conversation_id=conversation.id,
            consumed_at=now,
        )
        return ExchangedWidgetInvitation(
            organization_id=invitation.organization_id,
            contact_id=invitation.contact_id,
            conversation_id=conversation.id,
            session_token=session.session_token,
            session_expires_at=session.expires_at,
        )


async def _load_existing_exchange(
    invitation: WidgetInvitationModel,
    *,
    now: datetime,
    db,
) -> ExchangedWidgetInvitation:
    if invitation.session_id is None or invitation.conversation_id is None:
        raise WidgetInvitationUnavailable
    session = await db.get(AuthSessionModel, invitation.session_id)
    if (
        session is None
        or session.deleted
        or session.organization_id != invitation.organization_id
        or session.contact_id != invitation.contact_id
        or session.expires_at <= now
    ):
        raise WidgetInvitationUnavailable
    await ConversationService(db).get_by_organization_contact_and_id(
        invitation.organization_id,
        invitation.contact_id,
        invitation.conversation_id,
    )
    return ExchangedWidgetInvitation(
        organization_id=invitation.organization_id,
        contact_id=invitation.contact_id,
        conversation_id=invitation.conversation_id,
        session_token=session.session_token,
        session_expires_at=session.expires_at,
    )


def _build_invitation_url(token: str) -> str:
    base_url = str(settings.WIDGET_URL or "").strip()
    parsed = urlparse(base_url)
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    if (
        not base_url
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or (parsed.scheme != "https" and not local_http)
        or parsed.query
        or parsed.fragment
    ):
        raise WidgetInvitationConfigurationError(
            "WIDGET_URL must be an explicit HTTPS origin (local HTTP is allowed)."
        )
    return f"{base_url.rstrip('/')}?invitation={quote(token, safe='')}"


__all__ = [
    "ExchangedWidgetInvitation",
    "IssuedWidgetInvitation",
    "exchange_widget_invitation",
    "issue_widget_invitation",
]
