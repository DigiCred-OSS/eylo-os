"""Direction-aware conversation bootstrap for carrier media sessions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, WebSocket, status

from eylo.common.database import start_transaction
from eylo.modules.agents.domain import ResolvedExecutableAgent
from eylo.modules.auth.schemas import SessionInitiateRequest
from eylo.modules.auth.services.session_service import AuthSessionService
from eylo.modules.conversations.models.conversations import ConversationChannels
from eylo.modules.conversations.schemas.conversations import (
    ConversationInitialMessage,
    ConversationInitialMessageContent,
    ConversationMessageRequest,
    ConversationParticipant,
    ConversationParticipantProfile,
    ConversationParticipantProfileContactKind,
    ConversationStartRequest,
)
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.telephony.lifecycle import record_opener_delivery
from eylo.modules.user_sessions.domain import UserSessionEntryChannel
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.user_sessions.service import UserSessionService
from eylo.pipelines.websocket.singleton import S_ws_manager
from eylo.sockets.telephony.base import CallMetadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConversationBundle:
    """Authenticated contact session and its new phone conversation."""

    auth_session_token: str
    conversation_id: UUID
    contact_id: UUID
    user_session_id: UUID


async def init_conversation(
    *,
    organization_id: UUID,
    agent_id: UUID,
    executable_agent: ResolvedExecutableAgent,
    from_number: str,
    to_number: str,
    call_metadata: CallMetadata,
    stream_sid: str | None,
    wire_ws: WebSocket,
    provider: str,
) -> ConversationBundle:
    """Create one direction-correct contact, WS session, and conversation."""
    contact_number = _contact_number(call_metadata, from_number, to_number)
    auth_session_token: str | None = None
    registered = False
    try:
        async with start_transaction() as db_session:
            auth_service = AuthSessionService(db=db_session)
            initiation = await auth_service.initiate_widget_session_with_resolution(
                SessionInitiateRequest(
                    organization_id=organization_id,
                    external_id=contact_number,
                    primary_email=None,
                    primary_phone=contact_number,
                    name=None,
                    preferences=None,
                    user_agent=None,
                    ip_address=None,
                )
            )
            auth_session = initiation.session
            auth_session_token = auth_session.session_token
            session = await auth_service.validate_session_token(auth_session_token)
            if not session or not session.contact_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                )

            user_session_service = UserSessionService(db_session)
            started = await user_session_service.start_or_resume(
                organization_id=organization_id,
                contact_id=session.contact_id,
                entry_channel=UserSessionEntryChannel.TELEPHONY,
            )
            user_session_id = started.user_session.id

            registered = await S_ws_manager.register_telephony_session(
                websocket=wire_ws,
                organization_id=organization_id,
                session_id=auth_session_token,
                contact_id=session.contact_id,
                user_session_id=user_session_id,
                stream_sid=stream_sid or "",
                provider=provider,
            )
            if not registered:
                raise RuntimeError("Telephony session registration was rejected.")

            conversation = await ConversationService(db_session).start_conversation(
                organization_id=organization_id,
                request=build_conversation_start_request(
                    agent_id=agent_id,
                    call_metadata=call_metadata,
                    from_number=from_number,
                    to_number=to_number,
                    provider=provider,
                ),
                resolved_agent=executable_agent,
            )
            await user_session_service.link_conversation(
                organization_id=organization_id,
                user_session_id=user_session_id,
                conversation_id=conversation.id,
            )
            await file_user_session_fact(
                db_session,
                organization_id=organization_id,
                user_session_id=user_session_id,
                subject_type="conversation",
                subject_id=conversation.id,
                event_type="conversation.started",
                payload={"channel": ConversationChannels.PHONE.value},
            )
            await S_ws_manager.associate_conversation_session(
                conversation_id=conversation.id,
                session_id=auth_session_token,
                organization_id=organization_id,
            )
            return ConversationBundle(
                auth_session_token=auth_session_token,
                conversation_id=conversation.id,
                contact_id=session.contact_id,
                user_session_id=user_session_id,
            )
    except BaseException:
        if registered and auth_session_token is not None:
            try:
                await S_ws_manager.disconnect(
                    organization_id,
                    auth_session_token,
                    reason="telephony_setup_failed",
                )
            except Exception:
                logger.warning(
                    "Telephony setup rollback could not remove the WS session."
                )
        raise


def build_conversation_start_request(
    *,
    agent_id: UUID,
    call_metadata: CallMetadata,
    from_number: str,
    to_number: str,
    provider: str,
) -> ConversationStartRequest:
    """Build a direction-correct conversation without synthetic user speech."""
    is_outbound = call_metadata.direction.upper() == "OUTBOUND"
    contact_number = _contact_number(call_metadata, from_number, to_number)
    contact = ConversationParticipant(
        kind=ParticipantKind.CONTACT,
        external_id=contact_number,
        profiles=[
            ConversationParticipantProfile(
                kind=ConversationParticipantProfileContactKind.PHONE,
                value=contact_number,
            )
        ],
    )
    agent = ConversationParticipant(kind=ParticipantKind.AGENT, id=agent_id)
    return ConversationStartRequest(
        **{
            "from": (agent if is_outbound else contact).model_dump(by_alias=True),
            "to": (contact if is_outbound else agent).model_dump(by_alias=True),
            "message": None,
            "context": {
                "direction": call_metadata.direction.upper(),
                "from": from_number,
                "to": to_number,
                "provider": provider,
            },
            "channel": ConversationChannels.PHONE,
        }
    )


async def persist_delivered_outbound_opener(
    *,
    conversation_id: UUID,
    organization_id: UUID,
    call_id: UUID,
    text: str,
) -> None:
    """Persist assistant history only after carrier delivery was accepted."""
    async with start_transaction() as db_session:
        service = ConversationService(db_session)
        conversation = await service.get_(conversation_id)
        if conversation.organization_id != organization_id:
            raise ValueError("Conversation is unavailable.")
        await service.handle_agent_message(
            conversation_id,
            ConversationMessageRequest(
                message=ConversationInitialMessage(
                    content=[ConversationInitialMessageContent(type="text", text=text)]
                )
            ),
        )
        await record_opener_delivery(
            call_id=call_id,
            organization_id=organization_id,
            accepted=True,
            db=db_session,
        )


def _contact_number(
    call_metadata: CallMetadata,
    from_number: str,
    to_number: str,
) -> str:
    contact_number = (
        to_number if call_metadata.direction.upper() == "OUTBOUND" else from_number
    )
    if not contact_number:
        raise ValueError("Call contact phone number is required.")
    return contact_number
