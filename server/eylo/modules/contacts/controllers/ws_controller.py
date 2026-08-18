"""Transport orchestration for the `contacts` domain."""

import logging

from fastapi import status

from eylo.common.contracts.websocket import (
    WsContactQueryEvent,
    WsEventAction,
    WsIdentifyEvent,
    WsRequestEvent,
    WsResponse,
    build_ws_error_response,
)
from eylo.common.database import start_transaction
from eylo.modules.contacts.schemas.api import ContactApiResponseSchema
from eylo.modules.contacts.schemas.indb import (
    ContactInDb,
    ContactRef,
)
from eylo.modules.contacts.service import ContactService
from eylo.modules.session_context.schemas import SessionContext

logger = logging.getLogger(__name__)


class ContactWsController:
    """Controller for handling contact-related operations."""

    def __init__(self):
        """Initialize the ContactController."""
        self.service = ContactService()

    async def _get_session_contact(self, ctx: SessionContext) -> ContactInDb | None:
        if not ctx.contact_id:
            return None
        async with start_transaction(ro=True):
            return await self.service.get_by_ref(
                ContactRef(
                    organization_id=ctx.organization_id,
                    contact_id=ctx.contact_id,
                )
            )

    async def handle_contact_query(self, event: WsRequestEvent, ctx: SessionContext):
        try:
            request = WsContactQueryEvent.model_validate(event.data or {})
            if (
                not ctx.contact_id
                or request.filters.conversation_ids
                or {str(contact_id) for contact_id in request.filters.contact_ids}
                != {str(ctx.contact_id)}
            ):
                return build_ws_error_response(
                    event,
                    organization_id=ctx.organization_id,
                    session_id=ctx.session_id,
                    message="Contact is not available.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            contact = await self._get_session_contact(ctx)
            if not contact:
                return build_ws_error_response(
                    event,
                    organization_id=ctx.organization_id,
                    session_id=ctx.session_id,
                    message="Contact is not available.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.CONTACT_QUERY,
                data=[
                    ContactApiResponseSchema.model_validate(contact).model_dump(
                        by_alias=True
                    )
                ],
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
            )
        except Exception as error:
            logger.error(
                "Contact query failed error_type=%s",
                type(error).__name__,
            )
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
            )

    async def handle_identify(
        self, event: WsRequestEvent, ctx: SessionContext
    ) -> WsResponse:
        """Report the contact already bound to the authenticated session."""
        try:
            WsIdentifyEvent.model_validate(event.data or {})
            contact = await self._get_session_contact(ctx)
            if not contact:
                return build_ws_error_response(
                    event,
                    organization_id=ctx.organization_id,
                    session_id=ctx.session_id,
                    message="Contact is not available.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            return WsResponse(
                status=status.HTTP_200_OK,
                kind=WsEventAction.CONTACT_IDENTIFIED,
                data=ContactApiResponseSchema.model_validate(contact).model_dump(
                    by_alias=True
                ),
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
                request_id=event.request_id,
            )
        except Exception as error:
            logger.error(
                "Contact identify failed error_type=%s",
                type(error).__name__,
            )
            return build_ws_error_response(
                event,
                organization_id=ctx.organization_id,
                session_id=ctx.session_id,
            )
