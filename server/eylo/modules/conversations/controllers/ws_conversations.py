"""Transport orchestration for the `conversations` domain."""

import logging
from uuid import UUID

from fastapi import status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.websocket import (
    WsConversationQueryEvent,
    WsConversationReadEvent,
    WsEventAction,
    WsRequestEvent,
    WsResponse,
    build_ws_error_response,
)
from eylo.common.database import start_transaction
from eylo.common.schemas import PaginationParams
from eylo.modules.agents.exceptions import AgentNotFoundError
from eylo.modules.contacts.schemas.indb import ContactInDb, ContactRef
from eylo.modules.contacts.service import ContactService
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.models.conversations import ConversationChannels
from eylo.modules.conversations.schemas.aggregates import (
    ConversationAggregateResponse,
)
from eylo.modules.conversations.schemas.conversations import (
    ConversationApiResponseSchema,
    ConversationParticipant,
    ConversationStartRequest,
)
from eylo.modules.conversations.schemas.messages import MessageKind
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.conversations.services.aggregates import (
    ConversationAggregateService,
)
from eylo.modules.conversations.services.conversations import (
    ConversationBaseService,
)
from eylo.modules.conversations.services.read_state import ConversationReadService
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.session_context.schemas import SessionContext
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.user_sessions.service import UserSessionService
from eylo.pipelines.conversation.start import start_conversation_for_new_work

logger = logging.getLogger(__name__)


def _not_configured_response(
    error: NotConfiguredError,
    *,
    ctx: SessionContext,
    request_id: str | None,
) -> WsResponse:
    return WsResponse(
        status=status.HTTP_409_CONFLICT,
        kind=WsEventAction.ERROR,
        data={
            "capability": error.capability.value,
            "missing": list(error.missing),
            "configure_via": error.configure_via,
        },
        organization_id=ctx.organization_id,
        session_id=ctx.session_id,
        request_id=request_id,
    )


class InvalidWidgetConversationStart(ValueError):
    """The request shape cannot represent authenticated widget ingress."""


def _canonicalize_widget_start_request(
    contact: ContactInDb,
    request: ConversationStartRequest,
) -> ConversationStartRequest:
    if (
        request.from_.kind != ParticipantKind.CONTACT
        or request.to_.kind != ParticipantKind.AGENT
        or request.to_.id is None
    ):
        raise InvalidWidgetConversationStart

    if request.from_.id is not None and request.from_.id != contact.id:
        raise ConversationNotFound
    if (
        request.from_.external_id is not None
        and request.from_.external_id != contact.external_id
    ):
        raise ConversationNotFound

    return request.model_copy(
        update={
            "channel": ConversationChannels.WIDGET,
            "from_": ConversationParticipant(
                kind=ParticipantKind.CONTACT,
                id=contact.id,
            ),
        }
    )


class ConversationWsController:
    def __init__(self, db: AsyncSession | None = None):
        self.conversation_base_service = ConversationBaseService(db)
        self.contact_service = ContactService(db)
        self.db = db

    async def _conversation_not_found(
        self,
        event: WsRequestEvent,
        ctx: SessionContext,
    ) -> WsResponse:
        return build_ws_error_response(
            event,
            organization_id=ctx.organization_id,
            session_id=ctx.session_id,
            message="Conversation not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    async def handle_conversation_aggregate_query(
        self,
        event: WsRequestEvent,
        ctx: SessionContext,
        contact_id: UUID | None,
    ) -> WsResponse:
        """Handle conversation query with aggregate data (contacts, agents, messages, participants).

        This replaces the need for multiple separate queries by returning all related
        data in a single response.
        """
        try:
            request = WsConversationQueryEvent.model_validate(event.data or {})

            if not contact_id:
                return await self._conversation_not_found(event, ctx)

            conversations_indb = []

            # Fetch conversations (either specific IDs or paginated list)
            async with start_transaction(ro=True):
                if ctx.authorized_conversation_id is not None:
                    if request.filters.conversation_ids and any(
                        not ctx.allows_conversation(conversation_id)
                        for conversation_id in request.filters.conversation_ids
                    ):
                        return await self._conversation_not_found(event, ctx)
                    try:
                        conversations_indb = await self.conversation_base_service.resolve_by_organization_contact_and_ids(
                            organization_id=ctx.organization_id,
                            contact_id=contact_id,
                            conversation_ids=[ctx.authorized_conversation_id],
                        )
                    except ConversationNotFound:
                        return await self._conversation_not_found(event, ctx)
                elif request.filters.conversation_ids:
                    try:
                        conversations_indb = await self.conversation_base_service.resolve_by_organization_contact_and_ids(
                            organization_id=ctx.organization_id,
                            contact_id=contact_id,
                            conversation_ids=request.filters.conversation_ids,
                        )
                    except ConversationNotFound:
                        return await self._conversation_not_found(event, ctx)
                else:
                    page_params = PaginationParams(
                        page=request.filters.page,
                        limit=request.filters.limit,
                        total=0,
                    )
                    conversations_indb = await self.conversation_base_service.filter_by_contact_organization(
                        organization_id=ctx.organization_id,
                        contact_id=contact_id,
                        offset=page_params.get_offset(),
                        limit=page_params.limit,
                    )

                if not conversations_indb:
                    return WsResponse(
                        status=status.HTTP_200_OK,
                        kind=WsEventAction.CONVERSATION_QUERY,
                        data=[],
                        organization_id=ctx.organization_id,
                        session_id=ctx.session_id,
                        request_id=event.request_id,
                    )

                # Fetch aggregated data for all conversations
                conversation_ids = [conv.id for conv in conversations_indb]

                service = ConversationAggregateService()
                # Use message_limit and message_offset from request for pagination
                message_limit = request.filters.message_limit
                message_offset = request.filters.message_offset

                aggregates = await service.get_conversations_with_relations(
                    conversation_ids=conversation_ids,
                    organization_id=ctx.organization_id,
                    include_messages=message_limit > 0,
                    message_limit=message_limit,
                    message_offset=message_offset,
                    include_participants=True,
                    message_kinds=[MessageKind.ASSISTANT, MessageKind.USER],
                )
                unread_counts = await ConversationReadService().unread_counts(
                    organization_id=ctx.organization_id,
                    contact_id=contact_id,
                    conversation_ids=conversation_ids,
                )
                aggregates = [
                    aggregate.model_copy(
                        update={"unread_count": unread_counts.get(aggregate.id, 0)}
                    )
                    for aggregate in aggregates
                ]

            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.CONVERSATION_QUERY,
                data=[
                    ConversationAggregateResponse.model_validate(agg).model_dump(
                        by_alias=True
                    )
                    for agg in aggregates
                ],
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
            )

        except Exception as error:
            logger.error(
                "Conversation aggregate query failed error_type=%s",
                type(error).__name__,
            )
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
            )

    async def handle_conversation_read(
        self,
        event: WsRequestEvent,
        ctx: SessionContext,
        contact_id: UUID | None,
    ) -> WsResponse:
        try:
            request = WsConversationReadEvent.model_validate(event.data or {})
            if not contact_id or not ctx.allows_conversation(request.conversation_id):
                return await self._conversation_not_found(event, ctx)
            async with start_transaction():
                read_at = await ConversationReadService().mark_read(
                    organization_id=ctx.organization_id,
                    contact_id=contact_id,
                    conversation_id=request.conversation_id,
                )
            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.CONVERSATION_READ,
                data={
                    "conversation_id": str(request.conversation_id),
                    "last_read_at": read_at.isoformat(),
                    "unread_count": 0,
                },
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
            )
        except (ConversationNotFound, ValidationError):
            return await self._conversation_not_found(event, ctx)

    async def handle_start_conversation(
        self,
        event: WsRequestEvent,
        ctx: SessionContext,
        contact_id: UUID | None,
    ) -> WsResponse:
        try:
            request = ConversationStartRequest.model_validate(event.data or {})
            if not contact_id or ctx.user_session_id is None:
                return await self._conversation_not_found(event, ctx)
            if ctx.authorized_conversation_id is not None:
                return await self._conversation_not_found(event, ctx)

            async with start_transaction() as db:
                user_sessions = UserSessionService(db)
                await user_sessions.require_contact_session(
                    organization_id=ctx.organization_id,
                    contact_id=contact_id,
                    user_session_id=ctx.user_session_id,
                )
                contact_indb = await self.contact_service.get_by_ref(
                    ContactRef(
                        organization_id=ctx.organization_id,
                        contact_id=contact_id,
                    )
                )
                if not contact_indb:
                    raise ConversationNotFound
                request = _canonicalize_widget_start_request(
                    contact_indb,
                    request,
                )
                conversation_indb = await start_conversation_for_new_work(
                    service=self.conversation_base_service,
                    organization_id=ctx.organization_id,
                    request=request,
                    db=self.db,
                )
                await user_sessions.link_conversation(
                    organization_id=ctx.organization_id,
                    user_session_id=ctx.user_session_id,
                    conversation_id=conversation_indb.id,
                )
                await file_user_session_fact(
                    db,
                    organization_id=ctx.organization_id,
                    user_session_id=ctx.user_session_id,
                    subject_type="conversation",
                    subject_id=conversation_indb.id,
                    event_type="conversation.started",
                    occurred_at=conversation_indb.created_at,
                    payload={
                        "channel": conversation_indb.channel.value,
                        "agent_id": str(request.to_.id),
                    },
                )
            logger.info(
                "Conversation started organization_id=%s conversation_id=%s",
                ctx.organization_id,
                conversation_indb.id,
            )
            ctx.ws.agent_id = request.to_.id

            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.CONVERSATION_CREATED,
                data=ConversationApiResponseSchema.model_validate(
                    conversation_indb
                ).model_dump(by_alias=True),
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
            )

        except NotConfiguredError as error:
            return _not_configured_response(
                error,
                ctx=ctx,
                request_id=event.request_id,
            )
        except (ConversationNotFound, AgentNotFoundError):
            return await self._conversation_not_found(event, ctx)
        except (InvalidWidgetConversationStart, ValidationError):
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Invalid conversation start request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as error:
            logger.error(
                "Conversation start failed error_type=%s",
                type(error).__name__,
            )
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                message="Unable to start conversation",
            )
