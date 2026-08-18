"""Persistence access for the `conversations` domain."""

from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update

from eylo.common.database import register_ephemeral_event_post_txn
from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.events.schema.py_events.base import ParticipantCreatedEvent
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.messages import MessageKind
from eylo.modules.conversations.schemas.participants import (
    ParticipantCreateSchema,
    ParticipantInDb,
    ParticipantKind,
)


class ConversationParticipantRepository(BaseORMRepository[ParticipantsModel]):
    @property
    def model(self) -> ParticipantsModel:
        return ParticipantsModel

    async def create_(self, participant: ParticipantCreateSchema) -> ParticipantsModel:
        entity = map_schema_to_model(
            self.model,
            participant,
        )
        return await self.save_(entity)

    async def get_by_conversation_id(
        self, conversation_id: str
    ) -> List[ParticipantsModel]:
        return await self.filter_all_(
            [
                self.model.conversation_id == conversation_id,
            ]
        )

    async def mark_contact_read(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        conversation_id: UUID,
        read_at: datetime,
    ) -> datetime | None:
        participant = await self.db_session.scalar(
            select(self.model)
            .join(
                ConversationsModel,
                ConversationsModel.id == self.model.conversation_id,
            )
            .where(
                ConversationsModel.id == conversation_id,
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
                self.model.conversation_id == conversation_id,
                self.model.entity_kind == ParticipantKind.CONTACT.value,
                self.model.entity_id == str(contact_id),
                self.model.is_active.is_(True),
                self.model.deleted.is_(False),
            )
            .with_for_update()
        )
        if participant is None:
            return None
        if participant.last_read_at is None or participant.last_read_at < read_at:
            participant.last_read_at = read_at
            await self.db_session.flush()
        return participant.last_read_at

    async def unread_assistant_counts(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        conversation_ids: list[UUID],
    ) -> dict[UUID, int]:
        if not conversation_ids:
            return {}
        rows = await self.db_session.execute(
            select(
                MessagesModel.conversation_id,
                func.count(MessagesModel.id),
            )
            .join(
                self.model,
                and_(
                    self.model.conversation_id == MessagesModel.conversation_id,
                    self.model.entity_kind == ParticipantKind.CONTACT.value,
                    self.model.entity_id == str(contact_id),
                    self.model.is_active.is_(True),
                    self.model.deleted.is_(False),
                ),
            )
            .join(
                ConversationsModel,
                ConversationsModel.id == MessagesModel.conversation_id,
            )
            .where(
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
                MessagesModel.conversation_id.in_(conversation_ids),
                MessagesModel.kind == MessageKind.ASSISTANT.value,
                MessagesModel.deleted.is_(False),
                MessagesModel.created_at >= self.model.joined_at,
                or_(
                    self.model.last_read_at.is_(None),
                    MessagesModel.created_at > self.model.last_read_at,
                ),
            )
            .group_by(MessagesModel.conversation_id)
        )
        return {conversation_id: int(count) for conversation_id, count in rows}

    async def switch_primary_agent(
        self,
        conversation_id: UUID,
        current_agent_id: UUID,
        current_agent_revision: int,
        new_agent_id: UUID,
        new_agent_revision: int,
    ) -> UUID:
        current_primary_id = await self.db_session.scalar(
            select(self.model.id)
            .where(
                and_(
                    self.model.conversation_id == conversation_id,
                    self.model.entity_id == str(current_agent_id),
                    self.model.agent_revision == current_agent_revision,
                    self.model.entity_kind == ParticipantKind.AGENT.value,
                    self.model.is_primary.is_(True),
                    self.model.is_active.is_(True),
                )
            )
            .with_for_update()
        )
        if current_primary_id is None:
            raise ValueError(
                "The expected current agent is no longer primary in this conversation."
            )

        new_primary = await self.db_session.scalar(
            select(self.model)
            .where(
                and_(
                    self.model.conversation_id == conversation_id,
                    self.model.entity_id == str(new_agent_id),
                    self.model.agent_revision == new_agent_revision,
                    self.model.entity_kind == ParticipantKind.AGENT.value,
                    self.model.is_active.is_(True),
                )
            )
            .with_for_update()
        )
        if new_primary is not None and new_primary.is_primary:
            raise ValueError("Conversation already has conflicting primary agents.")

        await self.db_session.execute(
            update(self.model)
            .where(self.model.id == current_primary_id)
            .values(is_primary=False)
        )

        if new_primary is None:
            new_primary = ParticipantsModel(
                conversation_id=conversation_id,
                entity_id=str(new_agent_id),
                agent_id=new_agent_id,
                agent_revision=new_agent_revision,
                entity_kind=ParticipantKind.AGENT.value,
                is_primary=True,
            )
            new_primary = await self.save_(new_primary)

            participant_indb = ParticipantInDb.model_validate(new_primary)
            register_ephemeral_event_post_txn(
                ParticipantCreatedEvent(
                    conversation_id=conversation_id,
                    participant_id=participant_indb.id,
                    participant=participant_indb,
                )
            )
        else:
            await self.db_session.execute(
                update(self.model)
                .where(self.model.id == new_primary.id)
                .values(is_primary=True)
            )
        return new_primary.id
