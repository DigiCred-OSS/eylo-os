"""Persistence access for the `conversations` domain."""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy import exists, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from eylo.common.database import get_transaction
from eylo.common.repositories import BaseORMRepository, map_schema_to_model
from eylo.common.revisions import RevisionAvailability
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.agents.models import AgentRevisionModel
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessageKind, MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.messages import MessageCreate, RequestStatus


@dataclass(frozen=True, slots=True)
class AgentRunOutputAuthority:
    organization_id: UUID
    user_session_id: UUID | None


@dataclass(frozen=True, slots=True)
class RequestTimelineAuthority:
    organization_id: UUID
    user_session_id: UUID
    conversation_id: UUID


class MessageRepository(BaseORMRepository[MessagesModel]):
    @property
    def model(self) -> type[MessagesModel]:
        return MessagesModel

    async def create_(self, message: MessageCreate) -> MessagesModel:
        entity = map_schema_to_model(
            self.model,
            message,
        )
        saved = await self.save_(entity)
        await self.db_session.execute(
            update(ConversationsModel)
            .where(
                ConversationsModel.id == message.conversation_id,
                ConversationsModel.deleted.is_(False),
            )
            .values(
                updated_at=func.greatest(
                    ConversationsModel.updated_at,
                    saved.created_at,
                )
            )
        )
        return saved

    async def get_conversation_organization(
        self,
        conversation_id: UUID,
    ) -> UUID | None:
        return await self.db_session.scalar(
            select(ConversationsModel.organization_id).where(
                ConversationsModel.id == conversation_id,
                ConversationsModel.deleted.is_(False),
            )
        )

    async def update_(self, message_id: UUID, data: dict) -> MessagesModel:
        """Update a message by its ID."""
        entity = await self.get_(message_id)
        if not entity:
            raise ValueError(f"Message with id {message_id} not found")
        for key, value in data.items():
            setattr(entity, key, value)
        return await self.save_(entity)

    async def list_by_conversation_id(
        self, conversation_id: UUID
    ) -> List[MessagesModel]:
        return await self.filter_all_(
            [
                self.model.conversation_id == conversation_id,
            ]
        )

    async def get_first_user_message(
        self, conversation_id: UUID
    ) -> Optional[MessagesModel]:
        query = (
            select(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.kind == MessageKind.USER,
            )
            .order_by(self.model.created_at.asc())
            .limit(1)
        )

        result = await self.db_session.execute(query)

        return result.scalar_one_or_none()

    async def get_first_by_conversation_and_kind(
        self, conversation_id: UUID, kind: MessageKind
    ) -> Optional[MessagesModel]:
        query = (
            select(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.kind == kind,
            )
            .order_by(self.model.created_at.asc())
            .limit(1)
        )

        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def update_first_by_request_id(
        self, request_id: UUID, data: dict
    ) -> Optional[MessagesModel]:
        """Finds the first message by request_id and updates it."""
        query = (
            select(self.model)
            .where(self.model.request_id == request_id)
            .order_by(self.model.created_at.asc())
            .limit(1)
        )
        result = await self.db_session.execute(query)
        entity = result.scalar_one_or_none()

        if entity:
            for key, value in data.items():
                setattr(entity, key, value)
            return await self.save_(entity)

    async def update_first_by_request_id_and_organization(
        self,
        request_id: UUID,
        organization_id: UUID,
        data: dict,
    ) -> Optional[MessagesModel]:
        query = (
            select(self.model)
            .join(
                ConversationsModel,
                self.model.conversation_id == ConversationsModel.id,
            )
            .where(
                self.model.request_id == request_id,
                self.model.deleted.is_(False),
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
            )
            .order_by(self.model.created_at.asc())
            .limit(1)
            .with_for_update()
        )
        entity = (await self.db_session.execute(query)).scalar_one_or_none()
        if not entity:
            return None
        for key, value in data.items():
            setattr(entity, key, value)
        return await self.save_(entity)

    async def update_first_by_request_id_organization_and_contact(
        self,
        request_id: UUID,
        organization_id: UUID,
        contact_id: UUID,
        conversation_id: UUID,
        data: dict,
    ) -> Optional[MessagesModel]:
        active_contact_participant = exists(
            select(1).where(
                ParticipantsModel.conversation_id == ConversationsModel.id,
                ParticipantsModel.entity_id == str(contact_id),
                ParticipantsModel.entity_kind == "CONTACT",
                ParticipantsModel.is_active.is_(True),
            )
        )
        query = (
            select(self.model)
            .join(
                ConversationsModel,
                self.model.conversation_id == ConversationsModel.id,
            )
            .where(
                self.model.request_id == request_id,
                self.model.conversation_id == conversation_id,
                self.model.deleted.is_(False),
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
                active_contact_participant,
            )
            .order_by(self.model.created_at.asc())
            .limit(1)
            .with_for_update()
        )
        entity = (await self.db_session.execute(query)).scalar_one_or_none()
        if not entity:
            return None
        for key, value in data.items():
            setattr(entity, key, value)
        return await self.save_(entity)

    async def get_first_user_message_by_request_id(
        self, request_id: UUID
    ) -> Optional[MessagesModel]:
        query = (
            select(self.model)
            .where(
                self.model.request_id == request_id,
                self.model.kind == MessageKind.USER,
            )
            .order_by(self.model.created_at.asc())
            .limit(1)
        )

        result = await self.db_session.execute(query)

        return result.scalar_one_or_none()

    async def get_parent_user_session_id(
        self,
        parent_message_id: UUID,
        conversation_id: UUID,
    ) -> UUID | None:
        return await self.db_session.scalar(
            select(self.model.user_session_id).where(
                self.model.id == parent_message_id,
                self.model.conversation_id == conversation_id,
                self.model.deleted.is_(False),
            )
        )

    async def get_request_user_session_id(
        self,
        request_id: UUID,
        conversation_id: UUID,
    ) -> UUID | None:
        return await self.db_session.scalar(
            select(self.model.user_session_id)
            .where(
                self.model.request_id == request_id,
                self.model.conversation_id == conversation_id,
                self.model.user_session_id.is_not(None),
                self.model.deleted.is_(False),
            )
            .order_by(self.model.created_at.asc(), self.model.id.asc())
            .limit(1)
        )

    async def get_request_timeline_authority(
        self,
        request_id: UUID,
        conversation_id: UUID,
    ) -> RequestTimelineAuthority | None:
        row = (
            await self.db_session.execute(
                select(
                    ConversationsModel.organization_id,
                    self.model.user_session_id,
                    self.model.conversation_id,
                )
                .join(
                    ConversationsModel,
                    ConversationsModel.id == self.model.conversation_id,
                )
                .where(
                    self.model.request_id == request_id,
                    self.model.conversation_id == conversation_id,
                    self.model.user_session_id.is_not(None),
                    self.model.deleted.is_(False),
                    ConversationsModel.deleted.is_(False),
                )
                .order_by(self.model.created_at.asc(), self.model.id.asc())
                .limit(1)
            )
        ).one_or_none()
        if row is None or row.user_session_id is None:
            return None
        return RequestTimelineAuthority(
            organization_id=row.organization_id,
            user_session_id=row.user_session_id,
            conversation_id=row.conversation_id,
        )

    async def get_next_pending_user_message(
        self, conversation_id: UUID
    ) -> Optional[MessagesModel]:
        query = (
            select(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.kind == MessageKind.USER,
                self.model.request_status == RequestStatus.PENDING,
            )
            .order_by(self.model.created_at.asc(), self.model.id.asc())
            .limit(1)
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_newest_pending_user_message(
        self, conversation_id: UUID
    ) -> Optional[MessagesModel]:
        query = (
            select(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.kind == MessageKind.USER,
                self.model.request_status == RequestStatus.PENDING,
            )
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .limit(1)
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def list_pending_user_messages(
        self,
        conversation_id: UUID,
    ) -> list[MessagesModel]:
        query = (
            select(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.kind == MessageKind.USER,
                self.model.request_status == RequestStatus.PENDING,
            )
            .order_by(self.model.created_at.asc(), self.model.id.asc())
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def count_pending_user_messages(self, conversation_id: UUID) -> int:
        return await self.count_(
            filters=[
                self.model.conversation_id == conversation_id,
                self.model.kind == MessageKind.USER,
                self.model.request_status == RequestStatus.PENDING,
            ]
        )

    async def get_latest_request_status(
        self,
        request_id: str | UUID,
        conversation_id: UUID,
    ) -> Optional[RequestStatus]:
        query = (
            select(self.model.request_status)
            .where(
                self.model.request_id == request_id,
                self.model.conversation_id == conversation_id,
                self.model.deleted.is_(False),
                self.model.request_status.is_not(None),
            )
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .limit(1)
        )
        result = await self.db_session.execute(query)
        status = result.scalar_one_or_none()
        if status is None:
            return None
        return status if isinstance(status, RequestStatus) else RequestStatus(status)

    async def update_request_status_by_request_id(
        self,
        request_id: str | UUID,
        conversation_id: UUID,
        request_status: RequestStatus,
    ) -> int:
        update_query = (
            update(self.model)
            .where(
                self.model.request_id == request_id,
                self.model.conversation_id == conversation_id,
                self.model.deleted.is_(False),
                self.model.request_status.is_distinct_from(request_status),
            )
            .values(
                **{
                    "request_status": request_status,
                }
            )
        )
        result = await self.db_session.execute(update_query)
        return result.rowcount or 0

    async def list_by_request_id(
        self,
        request_id: str | UUID,
        conversation_id: UUID,
    ) -> list[MessagesModel]:
        result = await self.db_session.scalars(
            select(self.model)
            .where(
                self.model.request_id == request_id,
                self.model.conversation_id == conversation_id,
                self.model.deleted.is_(False),
            )
            .order_by(self.model.created_at.asc(), self.model.id.asc())
        )
        return list(result.all())


class MessageAgentRunRepository:
    """Persistence seam joining conversation messages to durable agent runs."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session or get_transaction()

    async def acquire_filing_lock(self, idempotency_key: str) -> None:
        """Serialize one PostgreSQL transaction per stable filing identity."""
        await self.session.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended(:idempotency_key, 0))"
            ),
            {"idempotency_key": idempotency_key},
        )

    async def get_conversation_organization_for_sender(
        self,
        *,
        conversation_id: UUID,
        sender_participant_id: UUID,
    ) -> UUID | None:
        query = (
            select(ConversationsModel.organization_id)
            .join(
                ParticipantsModel,
                ParticipantsModel.conversation_id == ConversationsModel.id,
            )
            .where(
                ConversationsModel.id == conversation_id,
                ConversationsModel.deleted.is_(False),
                ParticipantsModel.id == sender_participant_id,
                ParticipantsModel.deleted.is_(False),
                ParticipantsModel.is_active.is_(True),
            )
            .with_for_update()
        )
        return (await self.session.execute(query)).scalar_one_or_none()

    async def has_active_agent_revision(
        self,
        *,
        conversation_id: UUID,
        organization_id: UUID,
        agent_id: UUID,
        agent_revision: int,
    ) -> bool:
        query = select(
            exists(
                select(1)
                .select_from(ParticipantsModel)
                .join(
                    AgentRevisionModel,
                    (AgentRevisionModel.agent_id == ParticipantsModel.agent_id)
                    & (
                        AgentRevisionModel.revision
                        == ParticipantsModel.agent_revision
                    ),
                )
                .where(
                    ParticipantsModel.conversation_id == conversation_id,
                    ParticipantsModel.agent_id == agent_id,
                    ParticipantsModel.agent_revision == agent_revision,
                    ParticipantsModel.is_active.is_(True),
                    ParticipantsModel.deleted.is_(False),
                    AgentRevisionModel.organization_id == organization_id,
                    AgentRevisionModel.availability
                    == RevisionAvailability.PUBLISHED.value,
                    AgentRevisionModel.deleted.is_(False),
                )
            )
        )
        return bool((await self.session.execute(query)).scalar_one())

    async def has_active_agent_sender_revision(
        self,
        *,
        conversation_id: UUID,
        organization_id: UUID,
        sender_participant_id: UUID,
        agent_id: UUID,
        agent_revision: int,
    ) -> bool:
        """Prove the task author is the pinned active conversation agent."""
        query = select(
            exists(
                select(1)
                .select_from(ParticipantsModel)
                .join(
                    AgentRevisionModel,
                    (AgentRevisionModel.agent_id == ParticipantsModel.agent_id)
                    & (
                        AgentRevisionModel.revision
                        == ParticipantsModel.agent_revision
                    ),
                )
                .where(
                    ParticipantsModel.id == sender_participant_id,
                    ParticipantsModel.conversation_id == conversation_id,
                    ParticipantsModel.agent_id == agent_id,
                    ParticipantsModel.agent_revision == agent_revision,
                    ParticipantsModel.is_active.is_(True),
                    ParticipantsModel.deleted.is_(False),
                    AgentRevisionModel.organization_id == organization_id,
                    AgentRevisionModel.availability
                    == RevisionAvailability.PUBLISHED.value,
                    AgentRevisionModel.deleted.is_(False),
                )
            )
        )
        return bool((await self.session.execute(query)).scalar_one())

    async def has_published_agent_revision(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        agent_revision: int,
    ) -> bool:
        """Prove a non-participant execution target is exact and executable."""
        query = select(
            exists(
                select(1).where(
                    AgentRevisionModel.organization_id == organization_id,
                    AgentRevisionModel.agent_id == agent_id,
                    AgentRevisionModel.revision == agent_revision,
                    AgentRevisionModel.availability
                    == RevisionAvailability.PUBLISHED.value,
                    AgentRevisionModel.deleted.is_(False),
                )
            )
        )
        return bool((await self.session.execute(query)).scalar_one())

    async def get_run_by_idempotency_key(
        self,
        *,
        organization_id: UUID,
        idempotency_key: str,
    ) -> AgentRunModel | None:
        query = select(AgentRunModel).where(
            AgentRunModel.organization_id == organization_id,
            AgentRunModel.idempotency_key == idempotency_key,
            AgentRunModel.deleted.is_(False),
        )
        return (await self.session.execute(query)).scalar_one_or_none()

    async def get_origin_message(
        self,
        *,
        organization_id: UUID,
        message_id: UUID,
    ) -> MessagesModel | None:
        query = (
            select(MessagesModel)
            .join(
                ConversationsModel,
                ConversationsModel.id == MessagesModel.conversation_id,
            )
            .where(
                MessagesModel.id == message_id,
                MessagesModel.deleted.is_(False),
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
            )
        )
        return (await self.session.execute(query)).scalar_one_or_none()

    async def output_run_matches_conversation(
        self,
        *,
        run_id: UUID,
        conversation_id: UUID,
        sender_participant_id: UUID,
    ) -> bool:
        origin_message = aliased(MessagesModel)
        query = select(
            exists(
                select(1)
                .select_from(AgentRunModel)
                .join(
                    origin_message,
                    origin_message.id == AgentRunModel.origin_message_id,
                )
                .join(
                    ConversationsModel,
                    ConversationsModel.id == origin_message.conversation_id,
                )
                .join(
                    ParticipantsModel,
                    ParticipantsModel.conversation_id == ConversationsModel.id,
                )
                .where(
                    AgentRunModel.id == run_id,
                    AgentRunModel.deleted.is_(False),
                    origin_message.conversation_id == conversation_id,
                    origin_message.deleted.is_(False),
                    ParticipantsModel.id == sender_participant_id,
                    ParticipantsModel.is_active.is_(True),
                    ParticipantsModel.deleted.is_(False),
                    ConversationsModel.organization_id
                    == AgentRunModel.organization_id,
                    ConversationsModel.deleted.is_(False),
                )
            )
        )
        return bool((await self.session.execute(query)).scalar_one())

    async def get_output_run_authority(
        self,
        *,
        run_id: UUID,
        conversation_id: UUID,
        sender_participant_id: UUID,
    ) -> AgentRunOutputAuthority | None:
        origin_message = aliased(MessagesModel)
        row = (
            await self.session.execute(
                select(
                    AgentRunModel.organization_id,
                    AgentRunModel.user_session_id,
                )
                .select_from(AgentRunModel)
                .join(
                    origin_message,
                    origin_message.id == AgentRunModel.origin_message_id,
                )
                .join(
                    ConversationsModel,
                    ConversationsModel.id == origin_message.conversation_id,
                )
                .join(
                    ParticipantsModel,
                    ParticipantsModel.conversation_id == ConversationsModel.id,
                )
                .where(
                    AgentRunModel.id == run_id,
                    AgentRunModel.deleted.is_(False),
                    origin_message.conversation_id == conversation_id,
                    origin_message.deleted.is_(False),
                    ParticipantsModel.id == sender_participant_id,
                    ParticipantsModel.is_active.is_(True),
                    ParticipantsModel.deleted.is_(False),
                    ConversationsModel.organization_id
                    == AgentRunModel.organization_id,
                    ConversationsModel.deleted.is_(False),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return AgentRunOutputAuthority(
            organization_id=row.organization_id,
            user_session_id=row.user_session_id,
        )
