"""Repository for managing conversation database operations.

This module contains the ConversationRepository class, which provides methods for
database operations related to conversations.
"""

from typing import Optional
from uuid import UUID

import arrow
from sqlalchemy import exists, select, update

from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.modules.conversations.models.conversations import (
    ConversationStatus,
    ConversationsModel,
)
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.conversations import ConversationCreate


class ConversationRepository(BaseORMRepository[ConversationsModel]):
    @property
    def model(self) -> type[ConversationsModel]:
        return ConversationsModel

    async def create_(self, conversation: ConversationCreate) -> ConversationsModel:
        entity = map_schema_to_model(self.model, conversation)
        return await self.save_(entity)

    async def get_by_organization_and_id(
        self, organization_id: UUID, pk: UUID, for_update: bool = False
    ) -> Optional[ConversationsModel]:
        query = (
            select(ConversationsModel)
            .where(
                ConversationsModel.id == pk,
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
            )
            .limit(1)
        )

        if for_update:
            query = query.with_for_update()

        return (await self.db_session.execute(query)).scalar_one_or_none()

    def _has_active_contact_participant(self, contact_id: UUID):
        return exists(
            select(1).where(
                ParticipantsModel.conversation_id == ConversationsModel.id,
                ParticipantsModel.entity_id == str(contact_id),
                ParticipantsModel.entity_kind == "CONTACT",
                ParticipantsModel.is_active.is_(True),
            )
        )

    async def get_by_organization_contact_and_id(
        self,
        organization_id: UUID,
        contact_id: UUID,
        pk: UUID,
    ) -> Optional[ConversationsModel]:
        query = (
            select(ConversationsModel)
            .where(
                ConversationsModel.id == pk,
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
                self._has_active_contact_participant(contact_id),
            )
            .limit(1)
        )
        return (await self.db_session.execute(query)).scalar_one_or_none()

    async def filter_by_contact_organization(
        self,
        organization_id: UUID,
        contact_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversationsModel]:
        """Filter conversations where a specific contact is a participant.

        Args:
            organization_id: The UUID of the organization
            contact_id: The UUID of the contact
            limit: Pagination limit
            offset: Pagination offset

        Returns:
            List of conversation models

        """
        query = (
            select(ConversationsModel)
            .where(
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
                self._has_active_contact_participant(contact_id),
            )
            .order_by(ConversationsModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def list_by_organization_contact_and_ids(
        self,
        organization_id: UUID,
        contact_id: UUID,
        conversation_ids: list[UUID],
    ) -> list[ConversationsModel]:
        if not conversation_ids:
            return []

        query = (
            select(ConversationsModel)
            .where(
                ConversationsModel.id.in_(conversation_ids),
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
                self._has_active_contact_participant(contact_id),
            )
            .order_by(ConversationsModel.created_at.desc())
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def list_by_ids(
        self,
        conversation_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ConversationsModel]:
        """Bulk fetch conversations by IDs within an organization.

        Args:
            conversation_ids: List of conversation IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of conversation models matching the IDs

        """
        if not conversation_ids:
            return []

        filters = [
            self.model.id.in_(conversation_ids),
            self.model.organization_id == organization_id,
            self.model.deleted.is_(False),
        ]
        return await self.filter_all_(filters=filters)

    async def filter_by_agent_organization(
        self,
        organization_id: UUID,
        agent_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversationsModel]:
        """Filter conversations where a specific agent is a participant.

        Args:
            organization_id: The UUID of the organization
            agent_id: The UUID of the agent
            limit: Pagination limit
            offset: Pagination offset

        Returns:
            List of conversation models

        """
        query = (
            select(ConversationsModel)
            .where(
                ConversationsModel.organization_id == organization_id,
            )
            .join(
                ParticipantsModel,
                ParticipantsModel.conversation_id == ConversationsModel.id,
            )
            .where(
                ParticipantsModel.entity_id == str(agent_id),
                ParticipantsModel.entity_kind == "AGENT",
            )
            .order_by(ConversationsModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def expire_old_conversations(self) -> list[UUID]:
        now_ = arrow.utcnow().floor("month")
        start_ = now_.shift(months=-2).datetime
        end_ = now_.shift(months=-1).datetime
        query = (
            update(ConversationsModel)
            .where(
                ConversationsModel.updated_at >= start_,
                ConversationsModel.updated_at < end_,
                ConversationsModel.status == ConversationStatus.ACTIVE,
            )
            .values(
                status=ConversationStatus.COMPLETED,
                updated_at=arrow.utcnow().datetime,
            )
            .returning(ConversationsModel.id)
        )
        # Queries are now automatically logged via event listener when DEBUG=True
        result = await self.db_session.execute(query)
        expired_ids = [row[0] for row in result.fetchall()]
        return expired_ids
