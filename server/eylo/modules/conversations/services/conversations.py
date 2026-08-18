"""Application services for the `conversations` domain."""

import logging
from typing import Optional, Type, TypedDict
from uuid import UUID

import arrow  # Third-party
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import register_ephemeral_event_post_txn  # First-party
from eylo.common.services import EyloBaseService
from eylo.common.utils.context_sanitizer import sanitize_context
from eylo.events.schema.py_events.base import ConversationCreatedEvent
from eylo.listeners.schema import ConversationUpdatedEvent
from eylo.modules.agents.domain import (
    InvalidSwarmDefinitionError,
    ResolvedExecutableAgent,
    ResolvedSwarmTopology,
)
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.repositories.conversations import (
    ConversationRepository,
)
from eylo.modules.conversations.schemas import ConversationCreate, ConversationInDb
from eylo.modules.conversations.schemas.conversations import (
    ConversationFilterSchema,
    ConversationMessageRequest,
    ConversationParticipant,
    ConversationStartRequest,
)
from eylo.modules.conversations.schemas.message_content import (
    IMAGE_URL_CONTENT_TYPE,
    TEXT_CONTENT_TYPE,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageInDb,
    MessageKind,
)
from eylo.modules.conversations.schemas.participants import (
    ParticipantCreateSchema,
    ParticipantInDb,
    ParticipantKind,
)
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)

logger = logging.getLogger(__name__)


class ConversationResult(TypedDict):
    """Conversation Result Type."""

    conversation: ConversationInDb
    participant: ParticipantInDb
    message: MessageInDb


class ConversationBaseService(EyloBaseService[ConversationInDb]):
    """ConversationBaseService behavior for the "conversations" domain."""

    @property
    def schema(self) -> Type[ConversationInDb]:
        """Returns the schema class for conversation entities.
        This property is used by the base service class for type validation.
        """
        return ConversationInDb

    @property
    def repository(self) -> ConversationRepository:
        """Returns the repository instance for conversation data access.
        This property provides access to the conversation repository for CRUD operations.
        """
        return self._repository

    @repository.setter
    def repository(self, value: ConversationRepository):
        """Sets the repository instance for conversation data access.
        This setter allows dependency injection for testing and flexibility.
        """
        self._repository = value

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initializes a new instance of the ConversationService class.

        Sets up the repository and dependent services with the provided database session.

        Args:
            db: Optional database session for data access operations

        """
        self._repository = ConversationRepository(db)
        self.message_service = MessageService(db)
        self.participant_service = ConversationParticipantService(db)

    async def get_by_organization_and_id(
        self,
        organization_id: UUID,
        pk: UUID,
        for_update: bool = False,
    ) -> Optional[ConversationInDb]:
        """Get Conversation By Organization and ID."""
        entity = await self.repository.get_by_organization_and_id(
            organization_id=organization_id,
            pk=pk,
            for_update=for_update,
        )
        if not entity:
            raise ConversationNotFound
        return self.orm_to_schema(entity)

    async def get_by_organization_contact_and_id(
        self,
        organization_id: UUID,
        contact_id: UUID,
        pk: UUID,
    ) -> ConversationInDb:
        entity = await self.repository.get_by_organization_contact_and_id(
            organization_id=organization_id,
            contact_id=contact_id,
            pk=pk,
        )
        if not entity:
            raise ConversationNotFound
        return self.orm_to_schema(entity)

    async def resolve_by_organization_contact_and_ids(
        self,
        organization_id: UUID,
        contact_id: UUID,
        conversation_ids: list[UUID],
    ) -> list[ConversationInDb]:
        requested_ids = set(conversation_ids)
        if not requested_ids:
            raise ConversationNotFound

        entities = await self.repository.list_by_organization_contact_and_ids(
            organization_id=organization_id,
            contact_id=contact_id,
            conversation_ids=list(requested_ids),
        )
        if {entity.id for entity in entities} != requested_ids:
            raise ConversationNotFound
        return self.orm_to_schema_list(entities)

    async def create_(
        self,
        conversation: ConversationCreate,
    ) -> ConversationInDb:
        """Create for the "conversations" domain."""
        entity = await self.repository.create_(conversation)
        conversation_indb = self.orm_to_schema(entity)
        register_ephemeral_event_post_txn(
            ConversationCreatedEvent(
                conversation_id=entity.id,
                organization_id=entity.organization_id,
                conversation=conversation_indb,
            )
        )
        return conversation_indb

    async def _get_or_create_contact(
        self, organization_id: UUID, participant: ConversationParticipant
    ):
        """Get or Create Contact."""
        if not participant.kind == ParticipantKind.CONTACT:
            raise ValueError("Participant must be of kind CONTACT")
        return await self.participant_service.get_or_create_contact(
            organization_id, participant
        )

    def _validate_agent(
        self,
        organization_id: UUID,
        participant: ConversationParticipant,
        resolved_agent: ResolvedExecutableAgent,
    ) -> ResolvedExecutableAgent:
        """Validate agent for the "conversations" domain."""
        if not participant.kind == ParticipantKind.AGENT:
            raise ValueError("Participant must be of kind AGENT")
        if (
            participant.id != resolved_agent.ref.definition_id
            or resolved_agent.agent.organization_id != organization_id
        ):
            raise ValueError("Resolved agent does not match the conversation request.")
        return resolved_agent

    async def start_conversation(
        self,
        organization_id: UUID,
        request: ConversationStartRequest,
        *,
        resolved_agent: ResolvedExecutableAgent,
        resolved_swarm: ResolvedSwarmTopology | None = None,
    ) -> ConversationInDb:
        """Start conversation for the "conversations" domain."""
        from_ = request.from_
        to_ = request.to_
        if from_.kind == to_.kind:
            raise ValueError("Participants must be of different kinds")
        # get or create a contact participant
        # validate the agent participant
        _agent = to_ if to_.kind == ParticipantKind.AGENT else from_
        _contact = from_ if from_.kind == ParticipantKind.CONTACT else to_
        if request.swarm_id is None and resolved_swarm is not None:
            raise InvalidSwarmDefinitionError(
                "Resolved swarm does not match the conversation request."
            )
        if request.swarm_id is not None:
            if (
                resolved_swarm is None
                or resolved_swarm.organization_id != organization_id
                or resolved_swarm.ref.definition_id != request.swarm_id
            ):
                raise InvalidSwarmDefinitionError(
                    "Resolved swarm does not match the conversation request."
                )
            entry_member = resolved_swarm.member_by_agent_id(_agent.id)
            if entry_member is None:
                raise InvalidSwarmDefinitionError(
                    "The selected entry agent is not in this swarm topology."
                )
            if resolved_agent.ref != entry_member.executable_agent.ref:
                raise InvalidSwarmDefinitionError(
                    "The admitted agent revision does not match the swarm entry member."
                )
            resolved_agent = entry_member.executable_agent
        resolved_agent = self._validate_agent(
            organization_id,
            _agent,
            resolved_agent,
        )
        valid_agent: AgentInDb = resolved_agent.agent
        valid_contact = await self._get_or_create_contact(organization_id, _contact)
        create_kwargs: dict = dict(
            organization_id=organization_id,
            title=f"{valid_contact.name or ''} Started a new conversation with {valid_agent.name or ''}",
            external_id=request.external_id,
            swarm_id=(
                resolved_swarm.ref.definition_id if resolved_swarm is not None else None
            ),
            swarm_revision=(
                resolved_swarm.ref.revision if resolved_swarm is not None else None
            ),
        )
        if request.channel:
            create_kwargs["channel"] = request.channel
        sanitized_ctx = sanitize_context(request.context)
        if sanitized_ctx:
            create_kwargs["meta"] = {"context": sanitized_ctx}
        conversation = await self.create_(ConversationCreate(**create_kwargs))
        participant_agent = await self.participant_service.create_(
            ParticipantCreateSchema(
                conversation_id=conversation.id,
                entity_id=valid_agent.id,
                entity_kind=ParticipantKind.AGENT,
                agent_id=valid_agent.id,
                agent_revision=resolved_agent.ref.revision,
                is_primary=True,
            )
        )
        participant_contact = await self.participant_service.create_(
            ParticipantCreateSchema(
                conversation_id=conversation.id,
                entity_id=valid_contact.id,
                entity_kind=ParticipantKind.CONTACT,
                is_primary=True,
            )
        )

        initiating_participant = (
            participant_contact
            if from_.kind == ParticipantKind.CONTACT
            else participant_agent
        )

        if request.message and request.message.content:
            await self._create_participant_message(
                conversation=conversation,
                participant=initiating_participant,
                request=ConversationMessageRequest(
                    message=request.message,
                    context=request.context,
                ),
            )
        return conversation

    async def handle_user_message(
        self, conversation_id: UUID, request: ConversationMessageRequest
    ):
        conversation = await self.get_(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation Not Found: {conversation_id=}")
        participants = await self.participant_service.list_by_conversation(
            conversation_id=conversation.id
        )
        participant_contact = next(
            (p for p in participants if p.entity_kind == ParticipantKind.CONTACT), None
        )

        if not participant_contact:
            raise ValueError("Contact participant not found")

        await self._create_participant_message(
            conversation=conversation,
            participant=participant_contact,
            request=request,
        )
        return conversation

    async def handle_agent_message(
        self,
        conversation_id: UUID,
        request: ConversationMessageRequest,
    ) -> ConversationInDb:
        """Persist an agent-authored message through the canonical participant."""
        conversation = await self.get_(conversation_id)
        participants = await self.participant_service.list_by_conversation(
            conversation_id=conversation.id
        )
        primary_agents = self.participant_service.filter_primary_agent_participant(
            participants
        )
        if len(primary_agents) != 1:
            raise ValueError("Conversation requires one primary agent participant.")
        await self._create_participant_message(
            conversation=conversation,
            participant=primary_agents[0],
            request=request,
        )
        return conversation

    async def _create_participant_message(
        self,
        conversation: ConversationInDb,
        participant: ParticipantInDb,
        request: ConversationMessageRequest,
    ):
        _messages = []
        if request.message and request.message.content:
            content_blocks = []
            for m in request.message.content:
                if m.type == TEXT_CONTENT_TYPE and m.text:
                    content_blocks.append({"type": TEXT_CONTENT_TYPE, "text": m.text})
                elif m.type == IMAGE_URL_CONTENT_TYPE and m.image_url:
                    content_blocks.append(
                        {
                            "type": IMAGE_URL_CONTENT_TYPE,
                            "image_url": m.image_url.model_dump(mode="json"),
                        }
                    )

            if participant.entity_kind == ParticipantKind.CONTACT:
                _messages.append(
                    {
                        "role": MessageKind.USER.value.lower(),
                        "content": content_blocks,
                    }
                )
            elif participant.entity_kind == ParticipantKind.AGENT:
                _messages.append(
                    {
                        "role": MessageKind.ASSISTANT.value.lower(),
                        "content": content_blocks,
                    }
                )
            else:
                raise ValueError(
                    f"Unsupported participant kind for initial message: {participant.entity_kind}"
                )
        elif request.message and request.message.content:
            raise ValueError("Only TEXT conversation content is currently supported")

        if participant.entity_kind == ParticipantKind.CONTACT:
            message_kind = MessageKind.USER
        elif participant.entity_kind == ParticipantKind.AGENT:
            message_kind = MessageKind.ASSISTANT
        else:
            raise ValueError(
                f"Unsupported participant kind for message persistence: {participant.entity_kind}"
            )

        await self.message_service.create_(
            MessageCreate(
                conversation_id=conversation.id,
                sender_participant_id=participant.id,
                kind=message_kind,
                content_kind=MessageContentKind.TEXT,
                content=_messages[0],
                meta=request.model_dump(),
                created_at=arrow.utcnow().datetime,
            )
        )

    async def filter_by_contact_organization(
        self,
        organization_id: UUID,
        contact_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ):
        conversations = await self.repository.filter_by_contact_organization(
            organization_id=organization_id,
            contact_id=contact_id,
            limit=limit,
            offset=offset,
        )
        return self.orm_to_schema_list(conversations)

    async def update(self, conversation: ConversationInDb) -> ConversationInDb:
        """Update an existing conversation entity."""
        entity = await self.repository.partial_update_(self.schema_to_orm(conversation))
        register_ephemeral_event_post_txn(
            ConversationUpdatedEvent(conversation=conversation)
        )
        return self.orm_to_schema(entity)


class ConversationService(ConversationBaseService):
    async def list_by_organization(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[ConversationFilterSchema] = None,
    ) -> list[ConversationInDb]:
        """List conversations by organization ID with pagination."""
        _filters = [
            self.repository.model.organization_id == organization_id,
        ]
        if filters and filters.conversation_ids:
            _filters.append(self.repository.model.id.in_(filters.conversation_ids))
        conversations = await self.repository.filter_(
            filters=_filters,
            limit=limit,
            offset=offset,
            order_by=[self.repository.model.created_at.desc()],
        )
        return self.orm_to_schema_list(conversations)

    async def count_by_organization(
        self,
        organization_id: UUID,
    ) -> int:
        """Count conversations by organization ID."""
        count = await self.repository.count_(
            filters=[
                self.repository.model.organization_id == organization_id,
            ]
        )
        return count

    async def list_by_ids(
        self,
        conversation_ids: list[UUID],
        organization_id: UUID,
    ) -> list[ConversationInDb]:
        """Bulk fetch conversations by IDs within an organization.

        Args:
            conversation_ids: List of conversation IDs to fetch
            organization_id: Organization ID for access control

        Returns:
            List of conversation schema objects matching the provided IDs

        """
        conversations = await self.repository.list_by_ids(
            conversation_ids=conversation_ids,
            organization_id=organization_id,
        )
        return self.orm_to_schema_list(conversations)

    async def list_by_agent_id(
        self,
        agent_id: UUID,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversationInDb]:
        """List conversations where a specific agent is a participant.

        Args:
            agent_id: The UUID of the agent
            organization_id: The UUID of the organization
            limit: Pagination limit
            offset: Pagination offset

        Returns:
            List of conversation schema objects

        """
        conversations = await self.repository.filter_by_agent_organization(
            organization_id=organization_id,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )
        return self.orm_to_schema_list(conversations)

    async def update_title(
        self,
        conversation_id: UUID,
        title: str,
    ) -> ConversationInDb:
        """Update the title of a conversation."""
        conversation = await self.get_(conversation_id)
        if not conversation:
            raise ConversationNotFound
        conversation.title = title
        conversation.has_triggered_title_generation = True
        return await self.update(conversation)

    async def expire_old_conversations(self) -> list[UUID]:
        return await self.repository.expire_old_conversations()
