"""Transport orchestration for the `auth` domain."""

from uuid import UUID

from fastapi import HTTPException, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.exceptions import EntityNotFound
from eylo.common.schemas import EyloBaseApiSchema
from eylo.modules.auth.services.public_session import (
    PublicSessionService,
    SessionValidationError,
)
from eylo.modules.contacts.schemas.api import ContactApiResponseSchema
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas.conversations import (
    ConversationApiResponseSchema,
)


class SessionValidationRequest(EyloBaseApiSchema):
    """Request payload for session validation."""

    organization_id: UUID = Field(..., description="Organization UUID")
    session_token: str = Field(..., description="Session token from auth_sessions")
    contact_id: UUID = Field(..., description="Contact UUID")
    conversation_id: UUID = Field(..., description="Conversation UUID")


class SessionValidationResponse(EyloBaseApiSchema):
    """Response payload for successful session validation."""

    organization_id: str
    session_token: str
    contact: ContactApiResponseSchema
    conversation: ConversationApiResponseSchema


class PublicSessionController:
    """Validate public sessions without exposing authentication internals."""

    def __init__(self, db: AsyncSession):
        """Initialize the public session controller.

        Args:
            db: Database session for transaction management

        """
        self.service = PublicSessionService(db)

    async def validate_session(
        self, request: SessionValidationRequest
    ) -> SessionValidationResponse:
        """Validate a session and return safe contact/conversation data.

        Args:
            request: Session validation request with UUIDs

        Returns:
            SessionValidationResponse with sanitized data

        Raises:
            HTTPException: With appropriate status code and safe error message

        """
        try:
            conversation, contact, _participant = await self.service.validate_session(
                organization_id=request.organization_id,
                session_token=request.session_token,
                contact_id=request.contact_id,
                conversation_id=request.conversation_id,
            )

            # Build response with only safe fields (snake_case will auto-convert to camelCase)
            return SessionValidationResponse(
                organization_id=str(request.organization_id),
                session_token=request.session_token,
                contact=ContactApiResponseSchema.model_validate(contact),
                conversation=ConversationApiResponseSchema.model_validate(conversation),
            )

        except SessionValidationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session validation failed",
            )
        except (EntityNotFound, ConversationNotFound):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requested resource not found",
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during session validation",
            )
