"""Application services for the `conversations` domain."""

from typing import List, Optional, Type
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import register_ephemeral_event_post_txn
from eylo.common.services import EyloBaseService
from eylo.events.schema.py_events.base import ParticipantCreatedEvent
from eylo.modules.contacts.schemas.indb import ContactCreateSchema, ContactRef
from eylo.modules.conversations.repositories.participants import (
    ConversationParticipantRepository,
)
from eylo.modules.conversations.schemas.conversations import (
    ConversationParticipant,
    ConversationParticipantProfileContactKind,
)
from eylo.modules.conversations.schemas.participants import (
    ParticipantCreateSchema,
    ParticipantInDb,
    ParticipantKind,
)


class ConversationParticipantService(EyloBaseService[ParticipantInDb]):
    @property
    def schema(self) -> Type[ParticipantInDb]:
        return ParticipantInDb

    @property
    def repository(self) -> ConversationParticipantRepository:
        return self._repository

    @repository.setter
    def repository(self, value: ConversationParticipantRepository):
        self._repository = value

    @staticmethod
    def filter_agent_participants(
        participants: List[ParticipantInDb],
    ) -> List[ParticipantInDb]:
        """Filter participants to only include agents."""
        return [p for p in participants if p.entity_kind == ParticipantKind.AGENT]

    @staticmethod
    def filter_primary_agent_participant(
        participants: List[ParticipantInDb],
    ) -> List[ParticipantInDb]:
        """Filter participants to only include agents."""
        return [
            p
            for p in participants
            if p.entity_kind == ParticipantKind.AGENT and p.is_primary
        ]

    @staticmethod
    def filter_contact_participants(
        participants: List[ParticipantInDb],
    ) -> List[ParticipantInDb]:
        """Filter participants to only include contacts."""
        return [p for p in participants if p.entity_kind == ParticipantKind.CONTACT]

    @staticmethod
    def filter_primary_contact_participant(
        participants: List[ParticipantInDb],
    ) -> List[ParticipantInDb]:
        """Filter participants to only include primary contacts."""
        return [
            p
            for p in participants
            if p.entity_kind == ParticipantKind.CONTACT and p.is_primary
        ]

    def __init__(self, db: Optional[AsyncSession] = None):
        from eylo.modules.contacts.service import ContactService

        self._repository = ConversationParticipantRepository(db)
        self.contact_service = ContactService(db)

    async def create_(self, participant: ParticipantCreateSchema) -> ParticipantInDb:
        db_participant = await self.repository.create_(participant)
        participant_indb = self.orm_to_schema(db_participant)
        register_ephemeral_event_post_txn(
            ParticipantCreatedEvent(
                conversation_id=participant.conversation_id,
                participant_id=participant_indb.id,
                participant=participant_indb,
            )
        )
        return participant_indb

    async def list_by_conversation(
        self, conversation_id: UUID
    ) -> List[ParticipantInDb]:
        """List participants for a conversation.

        Args:
        ----
            conversation_id (int): ID of the conversation

        Returns:
        -------
            List[ParticipantRead]: List of participants for the conversation

        """
        _filters = [self.repository.model.conversation_id == conversation_id]
        entities = await self.repository.filter_all_(filters=_filters)
        return self.orm_to_schema_list(entities)

    async def list_page_by_conversation(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        offset: int,
    ) -> List[ParticipantInDb]:
        """Return historical handoff participants without soft-deleted rows."""
        entities = await self.repository.filter_(
            filters=[
                self.repository.model.conversation_id == conversation_id,
                self.repository.model.deleted.is_(False),
            ],
            limit=limit,
            offset=offset,
            order_by=[
                self.repository.model.joined_at.asc(),
                self.repository.model.id.asc(),
            ],
        )
        return self.orm_to_schema_list(entities)

    async def count_by_conversation(self, *, conversation_id: UUID) -> int:
        return await self.repository.count_(
            filters=[
                self.repository.model.conversation_id == conversation_id,
                self.repository.model.deleted.is_(False),
            ]
        )

    async def list_by_conversations(
        self,
        conversation_ids: List[UUID],
    ) -> List[ParticipantInDb]:
        """List participants for multiple conversations.

        Args:
        ----
            conversation_id (int): ID of the conversation

        Returns:
        -------
            List[ParticipantRead]: List of participants for the conversation

        """
        _filters = [self.repository.model.conversation_id.in_(conversation_ids)]
        entities = await self.repository.filter_all_(filters=_filters)
        return self.orm_to_schema_list(entities)

    async def list_page_by_conversations(
        self,
        *,
        conversation_ids: List[UUID],
        limit: int,
        offset: int,
    ) -> List[ParticipantInDb]:
        entities = await self.repository.filter_(
            filters=[
                self.repository.model.conversation_id.in_(conversation_ids),
                self.repository.model.deleted.is_(False),
            ],
            limit=limit,
            offset=offset,
            order_by=[
                self.repository.model.conversation_id.asc(),
                self.repository.model.joined_at.asc(),
                self.repository.model.id.asc(),
            ],
        )
        return self.orm_to_schema_list(entities)

    async def count_by_conversations(
        self,
        *,
        conversation_ids: List[UUID],
    ) -> int:
        return await self.repository.count_(
            filters=[
                self.repository.model.conversation_id.in_(conversation_ids),
                self.repository.model.deleted.is_(False),
            ]
        )

    async def get_or_create_contact(
        self, organization_id: UUID, participant: ConversationParticipant
    ):
        _id = participant.id
        _external_id = participant.external_id
        _profiles = participant.profiles
        _emails = []
        _phones = []
        if _profiles:
            _emails: List[str] = [
                p.value
                for p in _profiles
                if p.kind == ConversationParticipantProfileContactKind.EMAIL
            ]
            _phones: List[str] = [
                p.value
                for p in _profiles
                if p.kind == ConversationParticipantProfileContactKind.PHONE
            ]
        resolution = await self.contact_service.resolve_identity(
            organization_id=organization_id,
            email=_emails[0] if _emails else None,
            phone=_phones[0] if _phones else None,
            external_id=_external_id,
            contact_id=_id,
        )
        contact = resolution.contact
        if contact is None:
            if _id is not None:
                raise ValueError("The identified contact does not exist.")

            resolution = await self.contact_service.resolve_or_create(
                ContactCreateSchema(
                    organization_id=organization_id,
                    external_id=_external_id,
                    primary_email=_emails[0] if _emails else None,
                    primary_phone=_phones[0] if _phones else None,
                )
            )
            contact = resolution.contact
        if contact is None:
            raise ValueError("Contact not found or created")

        # Participants use polymorphic text references, not a contact FK. Hold
        # the contact row through the surrounding conversation transaction so
        # deletion either sees this participant or wins and rejects the link.
        return await self.contact_service.require_active(
            ContactRef(
                organization_id=organization_id,
                contact_id=contact.id,
            ),
            for_update=True,
        )

    async def get_contact_participant_from_conversation(self, conversation_id: UUID):
        _filters = [
            self.repository.model.conversation_id == conversation_id,
            self.repository.model.entity_kind == ParticipantKind.CONTACT,
        ]
        entities = await self.repository.filter_(filters=_filters)
        return self.orm_to_schema_list(entities)

    async def switch_primary_agent(
        self,
        conversation_id: UUID,
        current_agent_id: UUID,
        current_agent_revision: int,
        new_agent_id: UUID,
        new_agent_revision: int,
    ) -> ParticipantInDb:
        new_primary_participant_id = await self.repository.switch_primary_agent(
            conversation_id,
            current_agent_id,
            current_agent_revision,
            new_agent_id,
            new_agent_revision,
        )
        return await self.get_(new_primary_participant_id)
