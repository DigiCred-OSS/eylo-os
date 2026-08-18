"""Application services for the `conversations` domain."""

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import UUID, uuid4

import nh3 as bleach
from pydantic import BaseModel
from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.background_task import TaskContent
from eylo.common.database import register_ephemeral_event_post_txn
from eylo.common.services import EyloBaseService
from eylo.events.schema.py_events.base import MessageCreatedEvent
from eylo.modules.agent_runs.budgets import reserve_agent_run_in_transaction
from eylo.modules.agent_runs.domain import (
    AgentRunOriginKind,
    InitiatingPrincipalKind,
    InitiatingPrincipalRef,
)
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.conversations.constants import REALTIME_MESSAGE_SOURCE
from eylo.modules.conversations.message_facts import file_voice_message_fact
from eylo.modules.conversations.repositories.messages import (
    MessageAgentRunRepository,
    MessageRepository,
)
from eylo.modules.conversations.schemas.message_content import (
    AssistantMessageContent,
    SystemMessageContent,
    TextContent,
    ToolResultContent,
    ToolResultMessageContent,
    ToolUseContent,
    ToolUseMessageContent,
    UserMessageContent,
    WidgetMessageContent,
    WidgetResponseMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageInDb,
    MessageKind,
    MessageRequestFeedback,
    RequestStatus,
)
from eylo.modules.conversations.schemas.request_status import (
    RequestStatusTransitionResult,
)
from eylo.modules.conversations.services.participants import (
    ConversationParticipantService,
)
from eylo.modules.conversations.services.request_status import RequestStatusService
from eylo.modules.user_sessions.events import file_user_session_fact

if TYPE_CHECKING:
    from eylo.modules.conversations.services.llm_readiness import (
        ConversationLLMReadinessService,
    )


@dataclass(frozen=True, slots=True)
class MessageAgentRunFiling:
    """Result of atomically filing one inbound message and durable run."""

    message: MessageInDb
    run_id: UUID
    created: bool


class MessageAgentRunNotFound(Exception):
    """Message/run authority is missing or outside the conversation scope."""


class MessageAgentRunConflict(Exception):
    """One stable filing identity was reused with different semantics."""


class MessageProjectionConflict(Exception):
    """A canonical projection lacks exact conversation/sender authority."""


class MessageService(EyloBaseService[MessageInDb]):
    @property
    def schema(self) -> type[MessageInDb]:
        return MessageInDb

    @property
    def repository(self) -> MessageRepository:
        return self._repository

    @repository.setter
    def repository(self, value: MessageRepository):
        self._repository = value

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        *,
        llm_readiness: "ConversationLLMReadinessService | None" = None,
    ):
        self._db = db
        self._repository = MessageRepository(db)
        self._agent_run_repository = MessageAgentRunRepository(db)
        self.participant_service = ConversationParticipantService(db)
        self.request_status_service = RequestStatusService(db)
        self._llm_readiness = llm_readiness

    def _cleanup_text(self, message: MessageCreate) -> MessageCreate:
        if isinstance(message.content, UserMessageContent):
            cleaned_blocks = []
            for content in message.content.content:
                if isinstance(content, TextContent):
                    cleaned_blocks.append(
                        content.model_copy(update={"text": bleach.clean(content.text)})
                    )
                else:
                    cleaned_blocks.append(content)
            message.content = UserMessageContent(content=cleaned_blocks)
        return message

    def _initialize_request_status(self, message: MessageCreate) -> MessageCreate:
        if (
            message.kind == MessageKind.USER
            and message.request_status is None
            and not _is_realtime_message(message)
        ):
            message.request_status = RequestStatus.PENDING
        return message

    async def create_(
        self,
        message: MessageCreate,
    ) -> MessageInDb:
        organization_id: UUID | None = None
        if message.agent_run_id is not None:
            if message.kind == MessageKind.USER:
                raise MessageAgentRunConflict(
                    "An inbound user message cannot be an agent-run output."
                )
            authority = await self._agent_run_repository.get_output_run_authority(
                run_id=message.agent_run_id,
                conversation_id=message.conversation_id,
                sender_participant_id=message.sender_participant_id,
            )
            if authority is None:
                raise MessageAgentRunNotFound
            organization_id = authority.organization_id
            if (
                message.user_session_id is not None
                and message.user_session_id != authority.user_session_id
            ):
                raise MessageAgentRunConflict(
                    "Agent-run output session does not match its run authority."
                )
            message.user_session_id = authority.user_session_id

        if message.kind == MessageKind.USER:
            readiness = self._llm_readiness
            if readiness is None:
                from eylo.modules.conversations.services.llm_readiness import (
                    ConversationLLMReadinessService,
                )

                readiness = ConversationLLMReadinessService(self._db)
            await readiness.ensure_ready(message.conversation_id)

        if message.request_id is None:
            message.request_id = uuid4()
        message = await self._inherit_user_session(message)
        message = self._initialize_request_status(message)
        message = self._cleanup_text(message)
        if message.user_session_id is not None and organization_id is None:
            organization_id = await self.repository.get_conversation_organization(
                message.conversation_id
            )
            if organization_id is None:
                raise MessageAgentRunNotFound
        return await self._persist(message, organization_id=organization_id)

    async def create_canonical_projection(
        self,
        *,
        organization_id: UUID,
        message: MessageCreate,
    ) -> MessageInDb:
        """Persist one already-completed projection under exact sender authority.

        Canonical projections describe work that already happened, so they must
        never enqueue a new user-message AgentRun or re-run LLM readiness. The
        organization/conversation/participant relationship is still reloaded
        and locked before persistence.
        """
        expected_content_kind = {
            MessageKind.USER.value: MessageContentKind.TEXT,
            MessageKind.ASSISTANT.value: MessageContentKind.TEXT,
            MessageKind.TOOL_USE.value: MessageContentKind.TOOL,
            MessageKind.TOOL_RESULT.value: MessageContentKind.TOOL,
        }.get(message.kind.value)
        if (
            expected_content_kind is None
            or message.content_kind != expected_content_kind
        ):
            raise MessageProjectionConflict(
                "Canonical projection message class is unsupported."
            )
        if (
            message.agent_run_id is not None
            or message.request_id is None
            or not message.external_id
            or message.request_status
            not in (
                RequestStatus.COMPLETED,
                RequestStatus.FAILED,
                RequestStatus.INTERRUPTED,
                RequestStatus.SKIPPED,
            )
        ):
            raise MessageProjectionConflict(
                "Canonical projection message authority is incomplete."
            )
        owner = (
            await self._agent_run_repository.get_conversation_organization_for_sender(
                conversation_id=message.conversation_id,
                sender_participant_id=message.sender_participant_id,
            )
        )
        if owner != organization_id:
            raise MessageProjectionConflict(
                "Canonical projection conversation authority is unavailable."
            )
        message = await self._inherit_user_session(message)
        return await self._persist(
            self._cleanup_text(message),
            organization_id=organization_id,
        )

    async def _persist(
        self,
        message: MessageCreate,
        *,
        organization_id: UUID | None,
    ) -> MessageInDb:
        """Store and emit one already-authorized, prepared message."""
        entity = await self.repository.create_(message)
        message_indb = self.orm_to_schema(entity)
        await file_voice_message_fact(
            session=self.repository.db_session,
            message=message_indb,
        )
        if message_indb.user_session_id is not None:
            if organization_id is None:
                raise MessageAgentRunNotFound
            await file_user_session_fact(
                self.repository.db_session,
                organization_id=organization_id,
                user_session_id=message_indb.user_session_id,
                subject_type="message",
                subject_id=message_indb.id,
                event_type="message.created",
                occurred_at=message_indb.created_at,
                payload={
                    "conversation_id": str(message_indb.conversation_id),
                    "kind": message_indb.kind.value,
                    "content_kind": message_indb.content_kind.value,
                    "request_id": (
                        str(message_indb.request_id)
                        if message_indb.request_id is not None
                        else None
                    ),
                    "request_status": (
                        message_indb.request_status.value
                        if message_indb.request_status is not None
                        else None
                    ),
                },
            )
        register_ephemeral_event_post_txn(
            MessageCreatedEvent(
                conversation_id=message.conversation_id,
                message_id=message_indb.id,
                message=message_indb,
            )
        )
        return self.orm_to_schema(message_indb)

    async def _inherit_user_session(
        self,
        message: MessageCreate,
    ) -> MessageCreate:
        if message.user_session_id is not None:
            return message
        inherited = None
        if message.parent_message_id is not None:
            inherited = await self.repository.get_parent_user_session_id(
                message.parent_message_id,
                message.conversation_id,
            )
        if inherited is None and message.request_id is not None:
            inherited = await self.repository.get_request_user_session_id(
                message.request_id,
                message.conversation_id,
            )
        if inherited is None:
            return message
        return message.model_copy(update={"user_session_id": inherited})

    async def create_with_agent_run(
        self,
        *,
        message: MessageCreate,
        principal: InitiatingPrincipalRef,
        agent_id: UUID,
        agent_revision: int,
        context_manifest: dict,
        goal: str,
        idempotency_key: str,
    ) -> MessageAgentRunFiling:
        """File one inbound message plus run in the caller's DB transaction."""
        if message.kind != MessageKind.USER:
            raise MessageAgentRunConflict("An AgentRun origin must be a user message.")
        return await self._file_message_agent_run(
            message=message,
            principal=principal,
            agent_id=agent_id,
            agent_revision=agent_revision,
            context_manifest=context_manifest,
            goal=goal,
            idempotency_key=idempotency_key,
            task_content=None,
        )

    async def create_task_with_agent_run(
        self,
        *,
        message: MessageCreate,
        principal: InitiatingPrincipalRef,
        agent_id: UUID,
        agent_revision: int,
        context_manifest: dict,
        idempotency_key: str,
    ) -> MessageAgentRunFiling:
        """Atomically file one agent-authored TASK message and its run."""
        if (
            message.kind != MessageKind.SYSTEM
            or message.content_kind != MessageContentKind.TASK
        ):
            raise MessageAgentRunConflict(
                "A parallel AgentRun origin must be a system task message."
            )
        if principal.kind is not InitiatingPrincipalKind.WORKER:
            raise MessageAgentRunConflict(
                "A parallel AgentRun must be initiated by an agent."
            )
        try:
            task_content = TaskContent.from_json(
                self.get_message_content(message.content)
            )
        except ValueError as error:
            raise MessageAgentRunConflict(
                "Parallel task content is invalid."
            ) from error
        if task_content.source_agent_id != principal.principal_id:
            raise MessageAgentRunConflict(
                "Parallel task source does not match its initiating agent."
            )
        if task_content.execution_agent_ref() != (agent_id, agent_revision):
            raise MessageAgentRunConflict(
                "Parallel task target does not match its AgentRun authority."
            )
        return await self._file_message_agent_run(
            message=message,
            principal=principal,
            agent_id=agent_id,
            agent_revision=agent_revision,
            context_manifest=context_manifest,
            goal=task_content.instruction,
            idempotency_key=idempotency_key,
            task_content=task_content,
        )

    async def _file_message_agent_run(
        self,
        *,
        message: MessageCreate,
        principal: InitiatingPrincipalRef,
        agent_id: UUID,
        agent_revision: int,
        context_manifest: dict,
        goal: str,
        idempotency_key: str,
        task_content: TaskContent | None,
    ) -> MessageAgentRunFiling:
        """Persist one validated message-origin run without committing."""
        if message.agent_run_id is not None:
            raise MessageAgentRunConflict("An origin message cannot be run output.")
        if not idempotency_key.strip() or len(idempotency_key) > 256:
            raise MessageAgentRunConflict(
                "Message AgentRun idempotency key must contain 1-256 characters."
            )
        if not goal.strip() or len(goal) > 16384:
            raise MessageAgentRunConflict(
                "Message AgentRun goal must contain 1-16384 characters."
            )

        normalized_context = to_jsonable_python(context_manifest)
        if not isinstance(normalized_context, dict):
            raise MessageAgentRunConflict(
                "AgentRun context manifest must be an object."
            )

        message = message.model_copy(deep=True)
        request_id_was_supplied = message.request_id is not None
        if message.request_id is None:
            message.request_id = uuid4()
        message = self._initialize_request_status(message)
        message = self._cleanup_text(message)
        message = await self._inherit_user_session(message)

        stored_key = f"message:{principal.organization_id}:{idempotency_key}"
        await self._agent_run_repository.acquire_filing_lock(stored_key)
        existing_run = await self._agent_run_repository.get_run_by_idempotency_key(
            organization_id=principal.organization_id,
            idempotency_key=stored_key,
        )
        if existing_run is not None:
            return await self._existing_filing(
                run=existing_run,
                message=message,
                principal=principal,
                agent_id=agent_id,
                agent_revision=agent_revision,
                context_manifest=normalized_context,
                goal=goal,
                request_id_was_supplied=request_id_was_supplied,
            )

        organization_id = (
            await self._agent_run_repository.get_conversation_organization_for_sender(
                conversation_id=message.conversation_id,
                sender_participant_id=message.sender_participant_id,
            )
        )
        if organization_id != principal.organization_id:
            raise MessageAgentRunNotFound
        if task_content is None:
            target_is_valid = (
                await self._agent_run_repository.has_active_agent_revision(
                    conversation_id=message.conversation_id,
                    organization_id=organization_id,
                    agent_id=agent_id,
                    agent_revision=agent_revision,
                )
            )
        else:
            source_is_valid = (
                await self._agent_run_repository.has_active_agent_sender_revision(
                    conversation_id=message.conversation_id,
                    organization_id=organization_id,
                    sender_participant_id=message.sender_participant_id,
                    agent_id=task_content.source_agent_id,
                    agent_revision=task_content.source_agent_revision,
                )
            )
            target_is_valid = (
                await self._agent_run_repository.has_published_agent_revision(
                    organization_id=organization_id,
                    agent_id=agent_id,
                    agent_revision=agent_revision,
                )
            )
            target_is_valid = source_is_valid and target_is_valid
        if not target_is_valid:
            raise MessageAgentRunNotFound

        created_message = await self._persist(
            message,
            organization_id=organization_id,
        )
        run = AgentRunModel(
            id=uuid4(),
            organization_id=organization_id,
            initiating_principal_kind=principal.kind,
            initiating_principal_id=principal.principal_id,
            agent_id=agent_id,
            agent_revision=agent_revision,
            origin_kind=AgentRunOriginKind.MESSAGE,
            origin_message_id=created_message.id,
            user_session_id=created_message.user_session_id,
            session_context_digest=_context_digest(normalized_context),
            context_manifest=normalized_context,
            idempotency_key=stored_key,
            goal=goal,
        )
        self.repository.db_session.add(run)
        await self.repository.db_session.flush()
        if run.user_session_id is not None:
            await file_user_session_fact(
                self.repository.db_session,
                organization_id=organization_id,
                user_session_id=run.user_session_id,
                subject_type="agent.run",
                subject_id=run.id,
                event_type="agent.run.queued",
                payload={
                    "agent_id": str(run.agent_id),
                    "agent_revision": run.agent_revision,
                    "conversation_id": str(created_message.conversation_id),
                    "origin_message_id": str(created_message.id),
                },
            )
        await reserve_agent_run_in_transaction(
            self.repository.db_session,
            organization_id=organization_id,
            run_id=run.id,
        )
        return MessageAgentRunFiling(
            message=created_message,
            run_id=run.id,
            created=True,
        )

    async def _existing_filing(
        self,
        *,
        run: AgentRunModel,
        message: MessageCreate,
        principal: InitiatingPrincipalRef,
        agent_id: UUID,
        agent_revision: int,
        context_manifest: dict,
        goal: str,
        request_id_was_supplied: bool,
    ) -> MessageAgentRunFiling:
        if run.origin_message_id is None:
            raise MessageAgentRunConflict(
                "Idempotency key belongs to a non-message AgentRun."
            )
        origin = await self._agent_run_repository.get_origin_message(
            organization_id=principal.organization_id,
            message_id=run.origin_message_id,
        )
        if origin is None or not _same_filing(
            run=run,
            origin=origin,
            message=message,
            principal=principal,
            agent_id=agent_id,
            agent_revision=agent_revision,
            context_manifest=context_manifest,
            goal=goal,
            request_id_was_supplied=request_id_was_supplied,
        ):
            raise MessageAgentRunConflict(
                "Idempotency key was already used for different AgentRun input."
            )
        return MessageAgentRunFiling(
            message=self.orm_to_schema(origin),
            run_id=run.id,
            created=False,
        )

    async def update_(self, message_id: UUID, data: dict) -> MessageInDb:
        """Update a message by its ID."""
        entity = await self.repository.update_(message_id, data)
        return self.orm_to_schema(entity)

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        order_desc: bool = False,
        kind: Optional[List[MessageKind]] = None,
    ) -> list[MessageInDb]:
        _filters = [self.repository.model.conversation_id == conversation_id]
        if kind:
            _filters.append(self.repository.model.kind.in_(kind))
        entities = await self.repository.filter_all_(
            filters=_filters,
            order_by=[
                self.repository.model.created_at.desc()
                if order_desc
                else self.repository.model.created_at.asc()
            ],
        )
        return self.orm_to_schema_list(entities)

    async def list_page_by_conversation(
        self,
        *,
        conversation_id: UUID,
        limit: int,
        offset: int,
    ) -> list[MessageInDb]:
        """Return one stable, chronological page for the operator transcript."""
        entities = await self.repository.filter_(
            filters=[
                self.repository.model.conversation_id == conversation_id,
                self.repository.model.deleted.is_(False),
            ],
            limit=limit,
            offset=offset,
            order_by=[
                self.repository.model.created_at.asc(),
                self.repository.model.id.asc(),
            ],
        )
        return self.orm_to_schema_list(entities)

    async def count_messages_by_conversation(
        self,
        conversation_id: UUID,
        message_kinds: Optional[List[MessageKind]] = None,
    ) -> int:
        _filters = [self.repository.model.conversation_id == conversation_id]
        _filters.append(self.repository.model.deleted.is_(False))
        if message_kinds:
            _filters.append(self.repository.model.kind.in_(message_kinds))
        count = await self.repository.count_(filters=_filters)
        return count

    async def list_by_conversations(
        self,
        conversation_ids: List[UUID],
        kind: Optional[List[MessageKind]] = None,
    ) -> list[MessageInDb]:
        _filters = [self.repository.model.conversation_id.in_(conversation_ids)]
        if kind:
            _filters.append(self.repository.model.kind.in_(kind))
        entities = await self.repository.filter_all_(filters=_filters)
        return self.orm_to_schema_list(entities)

    async def list_page_by_conversations(
        self,
        *,
        conversation_ids: List[UUID],
        limit: int,
        offset: int,
    ) -> list[MessageInDb]:
        entities = await self.repository.filter_(
            filters=[
                self.repository.model.conversation_id.in_(conversation_ids),
                self.repository.model.deleted.is_(False),
            ],
            limit=limit,
            offset=offset,
            order_by=[
                self.repository.model.conversation_id.asc(),
                self.repository.model.created_at.asc(),
                self.repository.model.id.asc(),
            ],
        )
        return self.orm_to_schema_list(entities)

    async def count_messages_by_conversations(
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

    async def update_request_feedback(
        self, request_id: UUID, feedback: MessageRequestFeedback
    ) -> Optional[MessageInDb]:
        """Update the request feedback for the first message matching the request_id."""
        entity = await self.repository.update_first_by_request_id(
            request_id, {"request_feedback": feedback.value}
        )
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def update_request_feedback_by_organization(
        self,
        organization_id: UUID,
        request_id: UUID,
        feedback: MessageRequestFeedback,
    ) -> Optional[MessageInDb]:
        """Update feedback only when the message belongs to an active org conversation."""
        entity = await self.repository.update_first_by_request_id_and_organization(
            request_id=request_id,
            organization_id=organization_id,
            data={"request_feedback": feedback.value},
        )
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def update_request_feedback_by_organization_and_contact(
        self,
        organization_id: UUID,
        contact_id: UUID,
        conversation_id: UUID,
        request_id: UUID,
        feedback: MessageRequestFeedback,
    ) -> Optional[MessageInDb]:
        entity = (
            await self.repository.update_first_by_request_id_organization_and_contact(
                request_id=request_id,
                organization_id=organization_id,
                contact_id=contact_id,
                conversation_id=conversation_id,
                data={"request_feedback": feedback.value},
            )
        )
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def list_by_request_id(
        self,
        request_id: UUID,
        conversation_id: UUID,
    ) -> list[MessageInDb]:
        _filters = [
            self.repository.model.request_id == request_id,
            self.repository.model.conversation_id == conversation_id,
        ]
        entities = await self.repository.filter_all_(
            filters=_filters,
            order_by=[self.repository.model.created_at.asc()],
        )
        return self.orm_to_schema_list(entities)

    async def update_request_status_by_request_id(
        self,
        request_id: str | UUID,
        request_status: RequestStatus,
        *,
        conversation_id: UUID,
    ) -> RequestStatusTransitionResult:
        return await self.request_status_service.transition_to(
            request_id=UUID(str(request_id)),
            requested_status=request_status,
            conversation_id=conversation_id,
        )

    async def mark_request_failed_if_non_terminal(
        self,
        request_id: UUID,
        *,
        conversation_id: UUID,
    ) -> int:
        return await self.request_status_service.mark_failed_if_non_terminal(
            request_id,
            conversation_id=conversation_id,
        )

    async def get_first_user_message_by_request_id(
        self, request_id: UUID
    ) -> Optional[MessageInDb]:
        entity = await self.repository.get_first_user_message_by_request_id(request_id)
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def get_next_pending_user_message(
        self, conversation_id: UUID
    ) -> Optional[MessageInDb]:
        entity = await self.repository.get_next_pending_user_message(conversation_id)
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def get_newest_pending_user_message(
        self,
        conversation_id: UUID,
    ) -> Optional[MessageInDb]:
        entity = await self.repository.get_newest_pending_user_message(conversation_id)
        if not entity:
            return None
        return self.orm_to_schema(entity)

    async def list_pending_user_messages(
        self,
        conversation_id: UUID,
    ) -> list[MessageInDb]:
        entities = await self.repository.list_pending_user_messages(conversation_id)
        return self.orm_to_schema_list(entities)

    async def count_pending_user_messages(self, conversation_id: UUID) -> int:
        return await self.repository.count_pending_user_messages(conversation_id)

    async def get_first_by_conversation_and_kind(
        self, conversation_id: UUID, kind: MessageKind
    ) -> Optional[MessageInDb]:
        entity = await self.repository.get_first_by_conversation_and_kind(
            conversation_id, kind
        )
        if not entity:
            return None
        return self.orm_to_schema(entity)

    @staticmethod
    def get_message_content(
        content_object: UserMessageContent
        | AssistantMessageContent
        | ToolUseMessageContent
        | ToolResultMessageContent
        | SystemMessageContent
        | WidgetMessageContent
        | WidgetResponseMessageContent
        | None,
    ) -> str:
        if not content_object:
            return ""

        content_field = content_object.content
        if isinstance(content_field, str):
            return content_field
        elif isinstance(content_field, TextContent):
            return content_field.text
        elif isinstance(content_field, list):
            return content_object.get_text_content()
        elif isinstance(content_field, dict):
            return content_field.get("text", "")
        elif isinstance(content_object, WidgetMessageContent):
            return content_object.get_text_content()
        elif isinstance(content_object, WidgetResponseMessageContent):
            return content_object.get_text_content()
        elif isinstance(content_field, ToolUseContent) or (
            isinstance(content_field, list)
            and content_field
            and isinstance(content_field[0], ToolResultContent)
        ):
            return ""

        return ""


def _is_realtime_message(message: MessageCreate) -> bool:
    meta = message.meta
    if meta is None:
        return False
    if isinstance(meta, dict):
        return meta.get("source") == REALTIME_MESSAGE_SOURCE
    return meta.get("source") == REALTIME_MESSAGE_SOURCE


def _context_digest(context_manifest: dict) -> str:
    encoded = json.dumps(
        context_manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256(encoded).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _same_filing(
    *,
    run: AgentRunModel,
    origin,
    message: MessageCreate,
    principal: InitiatingPrincipalRef,
    agent_id: UUID,
    agent_revision: int,
    context_manifest: dict,
    goal: str,
    request_id_was_supplied: bool,
) -> bool:
    same_request = (
        not request_id_was_supplied or origin.request_id == message.request_id
    )
    return (
        run.initiating_principal_kind == principal.kind
        and run.initiating_principal_id == principal.principal_id
        and run.agent_id == agent_id
        and run.agent_revision == agent_revision
        and run.session_context_digest == _context_digest(context_manifest)
        and run.context_manifest == context_manifest
        and run.goal == goal
        and origin.conversation_id == message.conversation_id
        and origin.user_session_id == message.user_session_id
        and run.user_session_id == message.user_session_id
        and origin.sender_participant_id == message.sender_participant_id
        and origin.agent_run_id is None
        and origin.kind == message.kind
        and origin.content_kind == message.content_kind
        and origin.content == _json_value(message.content)
        and origin.parent_message_id == message.parent_message_id
        and origin.request_status == message.request_status
        and origin.external_id == message.external_id
        and origin.meta == _json_value(message.meta)
        and same_request
    )
