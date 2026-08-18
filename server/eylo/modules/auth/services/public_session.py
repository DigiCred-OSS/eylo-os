"""Application services for the `auth` domain."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.exceptions import EntityNotFound
from eylo.modules.auth.services.session_service import AuthSessionService
from eylo.modules.contacts.schemas.indb import ContactInDb
from eylo.modules.contacts.service import ContactService
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.schemas import ConversationInDb
from eylo.modules.conversations.schemas.participants import ParticipantInDb
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.modules.organizations.services import OrganizationService


class SessionValidationError(Exception):
    """Raised when session validation fails."""

    pass


class PublicSessionService:
    """Public Session Service."""

    def __init__(self, db: AsyncSession):
        """Initialize the public session service.

        Args:
            db: Database session for data access operations

        """
        self.db = db
        self.auth_session_service = AuthSessionService(db)
        self.organization_service = OrganizationService(db)
        self.contact_service = ContactService(db)
        self.conversation_service = ConversationService(db)
        self.participant_service = ConversationParticipantService(db)

    async def validate_session(
        self,
        organization_id: UUID,
        session_token: str,
        contact_id: UUID,
        conversation_id: UUID,
    ) -> tuple[ConversationInDb, ContactInDb, ParticipantInDb]:
        """Validate a session by verifying auth session and all relationships.

        Performs comprehensive validation:
        1. Validates session token exists and not expired (from auth_sessions)
        2. Verifies session belongs to the specified organization
        3. Verifies session belongs to the specified contact
        4. Validates conversation exists and belongs to organization
        5. Verifies contact is a participant in the conversation

        Args:
            organization_id: Organization UUID
            session_token: Session token string (from auth_sessions.session_token)
            contact_id: Contact UUID
            conversation_id: Conversation UUID

        Returns:
            Tuple of (conversation, contact, participant)

        Raises:
            SessionValidationError: If any validation check fails
            EntityNotFound: If any entity is not found

        """
        # Step 1: Validate session token
        auth_session = await self.auth_session_service.validate_session_token(
            session_token
        )
        if not auth_session:
            raise SessionValidationError("Invalid or expired session token")

        # Step 2: Verify session belongs to correct organization
        if str(auth_session.organization_id) != str(organization_id):
            raise SessionValidationError(
                "Session does not belong to the specified organization"
            )

        # Step 3: Verify session belongs to correct contact
        if str(auth_session.contact_id) != str(contact_id):
            raise SessionValidationError(
                "Session does not belong to the specified contact"
            )

        # Step 4: Validate organization exists (redundant but explicit)
        organization = await self.organization_service.get_(organization_id)
        if not organization:
            raise EntityNotFound(f"Organization {organization_id} not found")

        # Step 5: Validate conversation exists and belongs to organization
        conversation = await self.conversation_service.get_by_organization_and_id(
            organization_id=organization_id,
            pk=conversation_id,
        )
        if not conversation:
            raise ConversationNotFound(
                f"Conversation {conversation_id} not found in organization {organization_id}"
            )

        # Step 6: Validate contact exists (should already exist from auth_session)
        contact = await self.contact_service.get_(contact_id)
        if not contact:
            raise EntityNotFound(f"Contact {contact_id} not found")

        # Redundant check: verify contact belongs to organization
        if str(contact.organization_id) != str(organization_id):
            raise SessionValidationError(
                "Contact does not belong to the specified organization"
            )

        # Step 7: Verify contact is a participant in the conversation
        participant = await self.participant_service.repository.filter_one_(
            filters=[
                self.participant_service.repository.model.conversation_id
                == conversation_id,
                self.participant_service.repository.model.entity_id == str(contact_id),
                self.participant_service.repository.model.entity_kind
                == "CONTACT",  # ParticipantKind.CONTACT
            ]
        )
        if not participant:
            raise SessionValidationError(
                "Contact is not a participant in the specified conversation"
            )

        # Convert ORM model to schema
        participant_schema = self.participant_service.orm_to_schema(participant)

        return conversation, contact, participant_schema
