"""Transport orchestration for the `conversations` domain."""

import logging
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.websocket import (
    WsEventAction,
    WsParticipantQueryEvent,
    WsRequestEvent,
    WsResponse,
    build_ws_error_response,
)
from eylo.common.database import start_transaction
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas.participants import ParticipantApiResponseSchema
from eylo.modules.conversations.services.conversations import (
    ConversationBaseService,
)
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.modules.session_context.schemas import SessionContext

logger = logging.getLogger(__name__)


class ParticipantWsController:
    def __init__(self, db: AsyncSession | None = None):
        self.conversation_base_service = ConversationBaseService(db)
        self.conversation_participant_service = ConversationParticipantService(db)

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

    async def handle_participant_query(
        self,
        event: WsRequestEvent,
        ctx: SessionContext,
        contact_id: UUID | None,
    ):
        try:
            request = WsParticipantQueryEvent.model_validate(event.data or {})
            if not request.filters.conversation_ids:
                return await self._conversation_not_found(event, ctx)

            if not contact_id:
                return await self._conversation_not_found(event, ctx)
            if any(
                not ctx.allows_conversation(conversation_id)
                for conversation_id in request.filters.conversation_ids
            ):
                return await self._conversation_not_found(event, ctx)

            async with start_transaction(ro=True):
                try:
                    conversations = await self.conversation_base_service.resolve_by_organization_contact_and_ids(
                        organization_id=ctx.organization_id,
                        contact_id=contact_id,
                        conversation_ids=request.filters.conversation_ids,
                    )
                except ConversationNotFound:
                    return await self._conversation_not_found(event, ctx)
                participants_indb = (
                    await self.conversation_participant_service.list_by_conversations(
                        [conversation.id for conversation in conversations]
                    )
                )

            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.PARTICIPANT_QUERY,
                data=[
                    ParticipantApiResponseSchema.model_validate(c).model_dump(
                        by_alias=True
                    )
                    for c in participants_indb
                ],
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
            )
        except Exception as error:
            logger.error(
                "Participant query failed error_type=%s",
                type(error).__name__,
            )
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
            )
