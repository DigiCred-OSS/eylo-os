"""Detach history and erase one organization-owned contact aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from absurd_sdk import AsyncTaskContext
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.absurd_work import TERMINAL_STATES, DurableState
from eylo.common.contracts.memory import MemoryLevel, MemoryScope
from eylo.common.database import start_transaction
from eylo.common.outbound import OutboundOwnerKind
from eylo.events.durable.models import EventOutboxModel
from eylo.modules.agent_runs.models import AgentRunModel
from eylo.modules.auth.models import AuthSessionModel, WidgetInvitationModel
from eylo.modules.connections.models import ConnectionModel, OAuthStateModel
from eylo.modules.contacts.domain import CONTACT_SUBJECT_TYPE, ContactLifecycle
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.conversations.constants import DELETED_CONTACT_ENTITY_ID
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionExecutionFailure,
)
from eylo.modules.knowledgebase.jobs import KnowledgeIngestionJobModel
from eylo.modules.memory.models import MemoryChangeModel, MemoryModel
from eylo.modules.telephony.lifecycle import is_terminal_call_status
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.modules.user_sessions.models import (
    UserSessionConversationModel,
    UserSessionModel,
)
from eylo.modules.voice_transcripts.constants import VoiceSessionStatus
from eylo.modules.voice_transcripts.models import VoiceSessionModel
from eylo.pipelines.deletions.memory_erasure import (
    MemoryOwnerGraphChanged,
    erase_memory_owner,
)
from eylo.pipelines.outbound.models import OutboundAttemptModel
from eylo.products.campaigns.constants import CampaignContactStatus
from eylo.products.campaigns.models import (
    CampaignAttemptModel,
    CampaignContactModel,
    CampaignModel,
)

CONTACT_WORK_POLL_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class _ContactScope:
    contact: ContactsModel
    campaigns: tuple[CampaignModel, ...]
    campaign_contacts: tuple[CampaignContactModel, ...]
    attempts: tuple[CampaignAttemptModel, ...]
    calls: tuple[TelephonyCallModel, ...]
    voice_sessions: tuple[VoiceSessionModel, ...]
    conversations: tuple[ConversationsModel, ...]
    participants: tuple[ParticipantsModel, ...]
    user_sessions: tuple[UserSessionModel, ...]


class _ContactGraphChanged(Exception):
    """Contact-owned or contact-linked work changed while it was locked."""


class _OwnershipConflict(Exception):
    """The requested contact is not fenced for exact organization erasure."""


class ContactErasure:
    """Fence new work, wait for started work, then erase and detach atomically."""

    async def execute(
        self,
        *,
        organization_id: UUID,
        contact_id: UUID,
        task_context: AsyncTaskContext,
    ) -> None:
        wait_number = 0
        while True:
            try:
                should_wait = await _quiesce_contact_work(
                    organization_id=organization_id,
                    contact_id=contact_id,
                )
            except _ContactGraphChanged:
                should_wait = True
            except _OwnershipConflict as error:
                raise DeletionExecutionFailure(
                    DeletionErrorCode.ERASURE_FAILED,
                    retryable=False,
                ) from error
            except Exception as error:
                raise DeletionExecutionFailure(
                    DeletionErrorCode.DEPENDENCY_UNAVAILABLE,
                    retryable=True,
                ) from error

            if should_wait:
                wait_number += 1
                await task_context.sleep_for(
                    f"wait-contact-active-work-{wait_number}",
                    CONTACT_WORK_POLL_SECONDS,
                )
                continue

            try:
                await _erase_contact_graph(
                    organization_id=organization_id,
                    contact_id=contact_id,
                )
            except _ContactGraphChanged:
                wait_number += 1
                await task_context.sleep_for(
                    f"wait-contact-graph-stable-{wait_number}",
                    CONTACT_WORK_POLL_SECONDS,
                )
                continue
            except MemoryOwnerGraphChanged:
                wait_number += 1
                await task_context.sleep_for(
                    f"wait-contact-memory-stable-{wait_number}",
                    CONTACT_WORK_POLL_SECONDS,
                )
                continue
            except _OwnershipConflict as error:
                raise DeletionExecutionFailure(
                    DeletionErrorCode.ERASURE_FAILED,
                    retryable=False,
                ) from error
            except DeletionExecutionFailure:
                raise
            except Exception as error:
                raise DeletionExecutionFailure(
                    DeletionErrorCode.ERASURE_FAILED,
                    retryable=True,
                ) from error
            return


async def erase_contact(
    *,
    organization_id: UUID,
    contact_id: UUID,
    task_context: AsyncTaskContext,
) -> None:
    await ContactErasure().execute(
        organization_id=organization_id,
        contact_id=contact_id,
        task_context=task_context,
    )


async def _quiesce_contact_work(
    *,
    organization_id: UUID,
    contact_id: UUID,
) -> bool:
    async with start_transaction() as session:
        scope = await _lock_contact_scope(
            session,
            organization_id=organization_id,
            contact_id=contact_id,
        )
        if scope is None:
            return False
        _require_deletion_fence(scope.contact)
        _cancel_unstarted_attempts(scope)
        return _scope_requires_wait(scope)


async def _erase_contact_graph(
    *,
    organization_id: UUID,
    contact_id: UUID,
) -> None:
    async with start_transaction() as session:
        scope = await _lock_contact_scope(
            session,
            organization_id=organization_id,
            contact_id=contact_id,
        )
        if scope is None:
            return
        _require_deletion_fence(scope.contact)
        _cancel_unstarted_attempts(scope)
        if _scope_requires_wait(scope):
            raise _ContactGraphChanged

        campaign_contact_ids = {row.id for row in scope.campaign_contacts}
        attempt_ids = {row.id for row in scope.attempts}
        user_session_ids = {row.id for row in scope.user_sessions}
        contact_reference = str(contact_id)

        for participant in scope.participants:
            if (
                participant.entity_kind == ParticipantKind.CONTACT.value
                and participant.entity_id == contact_reference
            ):
                participant.entity_id = DELETED_CONTACT_ENTITY_ID
            if (
                participant.added_by_kind == ParticipantKind.CONTACT.value
                and participant.added_by_id == contact_reference
            ):
                participant.added_by_id = DELETED_CONTACT_ENTITY_ID
            if (
                participant.removed_by_kind == ParticipantKind.CONTACT.value
                and participant.removed_by_id == contact_reference
            ):
                participant.removed_by_id = DELETED_CONTACT_ENTITY_ID

        for conversation in scope.conversations:
            _detach_conversation(
                conversation,
                campaign_contact_ids=campaign_contact_ids,
                attempt_ids=attempt_ids,
            )

        for call in scope.calls:
            if call.campaign_contact_id in campaign_contact_ids:
                call.campaign_contact_id = None
            if call.campaign_attempt_id in attempt_ids:
                call.campaign_attempt_id = None

        if attempt_ids:
            await session.execute(
                delete(OutboundAttemptModel).where(
                    OutboundAttemptModel.organization_id == organization_id,
                    OutboundAttemptModel.owner_kind
                    == OutboundOwnerKind.CAMPAIGN_ATTEMPT,
                    OutboundAttemptModel.owner_id.in_(attempt_ids),
                )
            )
        await session.execute(
            delete(EventOutboxModel).where(
                EventOutboxModel.organization_id == organization_id,
                EventOutboxModel.subject_type == CONTACT_SUBJECT_TYPE,
                EventOutboxModel.subject_id == contact_id,
            )
        )
        if user_session_ids:
            await _detach_user_session_references(
                session,
                organization_id=organization_id,
                user_session_ids=user_session_ids,
            )
        await session.execute(
            delete(OAuthStateModel).where(
                OAuthStateModel.organization_id == organization_id,
                OAuthStateModel.contact_id == contact_id,
            )
        )
        await session.execute(
            delete(ConnectionModel).where(
                ConnectionModel.organization_id == organization_id,
                ConnectionModel.contact_id == contact_id,
            )
        )
        await session.execute(
            delete(WidgetInvitationModel).where(
                WidgetInvitationModel.organization_id == organization_id,
                WidgetInvitationModel.contact_id == contact_id,
            )
        )
        await session.execute(
            delete(AuthSessionModel).where(
                AuthSessionModel.organization_id == organization_id,
                AuthSessionModel.contact_id == contact_id,
            )
        )
        if attempt_ids:
            await session.execute(
                delete(CampaignAttemptModel).where(
                    CampaignAttemptModel.organization_id == organization_id,
                    CampaignAttemptModel.id.in_(attempt_ids),
                )
            )
        if campaign_contact_ids:
            await session.execute(
                delete(CampaignContactModel).where(
                    CampaignContactModel.organization_id == organization_id,
                    CampaignContactModel.id.in_(campaign_contact_ids),
                )
            )
        await erase_memory_owner(
            session,
            MemoryScope(
                organization_id=organization_id,
                level=MemoryLevel.USER,
                owner_id=contact_id,
            ),
        )
        if user_session_ids:
            await session.execute(
                delete(UserSessionModel).where(
                    UserSessionModel.organization_id == organization_id,
                    UserSessionModel.id.in_(user_session_ids),
                )
            )
        await _refresh_campaign_counts(session, scope.campaigns)
        await session.execute(
            delete(ContactsModel).where(
                ContactsModel.organization_id == organization_id,
                ContactsModel.id == contact_id,
            )
        )
        await session.flush()
        await _require_contact_absent(
            session,
            organization_id=organization_id,
            contact_id=contact_id,
            contact_reference=contact_reference,
            campaign_contact_ids=campaign_contact_ids,
            attempt_ids=attempt_ids,
            user_session_ids=user_session_ids,
        )


async def _lock_contact_scope(
    session: AsyncSession,
    *,
    organization_id: UUID,
    contact_id: UUID,
) -> _ContactScope | None:
    exists = await session.scalar(
        select(ContactsModel.id).where(
            ContactsModel.organization_id == organization_id,
            ContactsModel.id == contact_id,
        )
    )
    if exists is None:
        return None

    candidate_contacts = tuple(
        (
            await session.scalars(
                select(CampaignContactModel).where(
                    CampaignContactModel.organization_id == organization_id,
                    CampaignContactModel.contact_id == contact_id,
                )
            )
        ).all()
    )
    candidate_contact_ids = {row.id for row in candidate_contacts}
    candidate_campaign_ids = {row.campaign_id for row in candidate_contacts}
    candidate_attempts = (
        tuple(
            (
                await session.scalars(
                    select(CampaignAttemptModel).where(
                        CampaignAttemptModel.organization_id == organization_id,
                        CampaignAttemptModel.campaign_contact_id.in_(
                            candidate_contact_ids
                        ),
                    )
                )
            ).all()
        )
        if candidate_contact_ids
        else ()
    )
    candidate_attempt_ids = {row.id for row in candidate_attempts}

    campaigns = (
        tuple(
            (
                await session.scalars(
                    select(CampaignModel)
                    .where(
                        CampaignModel.organization_id == organization_id,
                        CampaignModel.id.in_(candidate_campaign_ids),
                    )
                    .order_by(CampaignModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if candidate_campaign_ids
        else ()
    )
    attempts = (
        tuple(
            (
                await session.scalars(
                    select(CampaignAttemptModel)
                    .where(
                        CampaignAttemptModel.organization_id == organization_id,
                        CampaignAttemptModel.id.in_(candidate_attempt_ids),
                    )
                    .order_by(CampaignAttemptModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if candidate_attempt_ids
        else ()
    )
    campaign_contacts = (
        tuple(
            (
                await session.scalars(
                    select(CampaignContactModel)
                    .where(
                        CampaignContactModel.organization_id == organization_id,
                        CampaignContactModel.id.in_(candidate_contact_ids),
                    )
                    .order_by(CampaignContactModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if candidate_contact_ids
        else ()
    )
    contact = await session.scalar(
        select(ContactsModel)
        .where(
            ContactsModel.organization_id == organization_id,
            ContactsModel.id == contact_id,
        )
        .with_for_update()
    )
    if contact is None:
        return None

    user_sessions = tuple(
        (
            await session.scalars(
                select(UserSessionModel)
                .where(
                    UserSessionModel.organization_id == organization_id,
                    UserSessionModel.contact_id == contact_id,
                )
                .order_by(UserSessionModel.id)
                .with_for_update()
            )
        ).all()
    )

    current_contact_ids = set(
        (
            await session.scalars(
                select(CampaignContactModel.id).where(
                    CampaignContactModel.organization_id == organization_id,
                    CampaignContactModel.contact_id == contact_id,
                )
            )
        ).all()
    )
    if current_contact_ids != candidate_contact_ids:
        raise _ContactGraphChanged
    current_attempt_ids = (
        set(
            (
                await session.scalars(
                    select(CampaignAttemptModel.id).where(
                        CampaignAttemptModel.organization_id == organization_id,
                        CampaignAttemptModel.campaign_contact_id.in_(
                            current_contact_ids
                        ),
                    )
                )
            ).all()
        )
        if current_contact_ids
        else set()
    )
    if current_attempt_ids != candidate_attempt_ids:
        raise _ContactGraphChanged

    contact_reference = str(contact_id)
    participant_conversation_ids = set(
        (
            await session.scalars(
                select(ParticipantsModel.conversation_id)
                .join(
                    ConversationsModel,
                    ConversationsModel.id == ParticipantsModel.conversation_id,
                )
                .where(
                    ConversationsModel.organization_id == organization_id,
                    ParticipantsModel.entity_kind == ParticipantKind.CONTACT.value,
                    ParticipantsModel.entity_id == contact_reference,
                )
            )
        ).all()
    )
    attempt_external_ids = {
        f"campaign-attempt:{attempt_id}" for attempt_id in candidate_attempt_ids
    }
    widget_conversation_ids = (
        set(
            (
                await session.scalars(
                    select(ConversationsModel.id).where(
                        ConversationsModel.organization_id == organization_id,
                        ConversationsModel.external_id.in_(attempt_external_ids),
                    )
                )
            ).all()
        )
        if attempt_external_ids
        else set()
    )
    conversation_ids = participant_conversation_ids | widget_conversation_ids

    call_ownership = []
    if candidate_contact_ids:
        call_ownership.append(
            TelephonyCallModel.campaign_contact_id.in_(candidate_contact_ids)
        )
    if candidate_attempt_ids:
        call_ownership.append(
            TelephonyCallModel.campaign_attempt_id.in_(candidate_attempt_ids)
        )
    if conversation_ids:
        call_ownership.append(TelephonyCallModel.conversation_id.in_(conversation_ids))
    calls = (
        tuple(
            (
                await session.scalars(
                    select(TelephonyCallModel)
                    .where(
                        TelephonyCallModel.organization_id == organization_id,
                        or_(*call_ownership),
                    )
                    .order_by(TelephonyCallModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if call_ownership
        else ()
    )
    call_ids = {row.id for row in calls}
    conversation_ids.update(
        row.conversation_id for row in calls if row.conversation_id is not None
    )

    session_ownership = []
    if call_ids:
        session_ownership.append(VoiceSessionModel.telephony_call_id.in_(call_ids))
    if conversation_ids:
        session_ownership.append(
            VoiceSessionModel.conversation_id.in_(conversation_ids)
        )
    voice_sessions = (
        tuple(
            (
                await session.scalars(
                    select(VoiceSessionModel)
                    .where(
                        VoiceSessionModel.organization_id == organization_id,
                        or_(*session_ownership),
                    )
                    .order_by(VoiceSessionModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if session_ownership
        else ()
    )
    conversation_ids.update(row.conversation_id for row in voice_sessions)

    conversations = (
        tuple(
            (
                await session.scalars(
                    select(ConversationsModel)
                    .where(
                        ConversationsModel.organization_id == organization_id,
                        ConversationsModel.id.in_(conversation_ids),
                    )
                    .order_by(ConversationsModel.id)
                    .with_for_update()
                )
            ).all()
        )
        if conversation_ids
        else ()
    )
    participants = tuple(
        (
            await session.scalars(
                select(ParticipantsModel)
                .join(
                    ConversationsModel,
                    ConversationsModel.id == ParticipantsModel.conversation_id,
                )
                .where(
                    ConversationsModel.organization_id == organization_id,
                    or_(
                        (ParticipantsModel.entity_kind == ParticipantKind.CONTACT.value)
                        & (ParticipantsModel.entity_id == contact_reference),
                        (
                            ParticipantsModel.added_by_kind
                            == ParticipantKind.CONTACT.value
                        )
                        & (ParticipantsModel.added_by_id == contact_reference),
                        (
                            ParticipantsModel.removed_by_kind
                            == ParticipantKind.CONTACT.value
                        )
                        & (ParticipantsModel.removed_by_id == contact_reference),
                    ),
                )
                .order_by(ParticipantsModel.id)
                .with_for_update(of=ParticipantsModel)
            )
        ).all()
    )
    return _ContactScope(
        contact=contact,
        campaigns=campaigns,
        campaign_contacts=campaign_contacts,
        attempts=attempts,
        calls=calls,
        voice_sessions=voice_sessions,
        conversations=conversations,
        participants=participants,
        user_sessions=user_sessions,
    )


def _require_deletion_fence(contact: ContactsModel) -> None:
    if contact.lifecycle != ContactLifecycle.DELETION_PENDING.value:
        raise _OwnershipConflict


def _cancel_unstarted_attempts(scope: _ContactScope) -> None:
    now = datetime.now(timezone.utc)
    cancelled_contact_ids = set()
    for attempt in scope.attempts:
        if attempt.state in TERMINAL_STATES or attempt.effect_started_at is not None:
            continue
        attempt.state = DurableState.CANCELLED
        attempt.finished_at = now
        attempt.last_error = None
        cancelled_contact_ids.add(attempt.campaign_contact_id)
    for contact in scope.campaign_contacts:
        if contact.id in cancelled_contact_ids:
            contact.status = CampaignContactStatus.CANCELLED.value


def _scope_requires_wait(scope: _ContactScope) -> bool:
    if any(attempt.state not in TERMINAL_STATES for attempt in scope.attempts):
        return True
    if any(not is_terminal_call_status(call.status) for call in scope.calls):
        return True
    return any(
        session.status == VoiceSessionStatus.ACTIVE.value
        for session in scope.voice_sessions
    )


def _detach_conversation(
    conversation: ConversationsModel,
    *,
    campaign_contact_ids: set[UUID],
    attempt_ids: set[UUID],
) -> None:
    if conversation.external_id in {
        f"campaign-attempt:{attempt_id}" for attempt_id in attempt_ids
    }:
        conversation.external_id = None

    meta = dict(conversation.meta or {})
    context = dict(meta.get("context") or {})
    contact_value = context.get("campaign_contact_id")
    attempt_value = context.get("campaign_attempt_id")
    if contact_value in {str(value) for value in campaign_contact_ids}:
        context.pop("campaign_contact_id", None)
    if attempt_value in {str(value) for value in attempt_ids}:
        context.pop("campaign_attempt_id", None)
    if context != (meta.get("context") or {}):
        if context:
            meta["context"] = context
        else:
            meta.pop("context", None)
        conversation.meta = meta


async def _detach_user_session_references(
    session: AsyncSession,
    *,
    organization_id: UUID,
    user_session_ids: set[UUID],
) -> None:
    """Erase contact-owned session facts while retaining product history."""
    await session.execute(
        update(MessagesModel)
        .where(MessagesModel.user_session_id.in_(user_session_ids))
        .values(user_session_id=None)
    )
    for model in (
        AgentRunModel,
        VoiceSessionModel,
        TelephonyCallModel,
        KnowledgeIngestionJobModel,
    ):
        await session.execute(
            update(model)
            .where(
                model.organization_id == organization_id,
                model.user_session_id.in_(user_session_ids),
            )
            .values(user_session_id=None)
        )
    await session.execute(
        delete(EventOutboxModel).where(
            EventOutboxModel.organization_id == organization_id,
            EventOutboxModel.correlation_id.in_(user_session_ids),
        )
    )


async def _refresh_campaign_counts(
    session: AsyncSession,
    campaigns: tuple[CampaignModel, ...],
) -> None:
    for campaign in campaigns:
        counts = dict(
            (
                await session.execute(
                    select(
                        CampaignContactModel.status,
                        func.count(CampaignContactModel.id),
                    )
                    .where(
                        CampaignContactModel.organization_id
                        == campaign.organization_id,
                        CampaignContactModel.campaign_id == campaign.id,
                        CampaignContactModel.deleted.is_(False),
                    )
                    .group_by(CampaignContactModel.status)
                )
            ).all()
        )
        campaign.total_contacts = sum(counts.values())
        campaign.completed_contacts = counts.get(
            CampaignContactStatus.COMPLETED.value,
            0,
        )
        campaign.failed_contacts = sum(
            counts.get(status.value, 0)
            for status in (
                CampaignContactStatus.FAILED,
                CampaignContactStatus.SKIPPED,
            )
        )


async def _require_contact_absent(
    session: AsyncSession,
    *,
    organization_id: UUID,
    contact_id: UUID,
    contact_reference: str,
    campaign_contact_ids: set[UUID],
    attempt_ids: set[UUID],
    user_session_ids: set[UUID],
) -> None:
    checks = (
        select(ContactsModel.id).where(
            ContactsModel.organization_id == organization_id,
            ContactsModel.id == contact_id,
        ),
        select(AuthSessionModel.id).where(
            AuthSessionModel.organization_id == organization_id,
            AuthSessionModel.contact_id == contact_id,
        ),
        select(WidgetInvitationModel.id).where(
            WidgetInvitationModel.organization_id == organization_id,
            WidgetInvitationModel.contact_id == contact_id,
        ),
        select(ConnectionModel.id).where(
            ConnectionModel.organization_id == organization_id,
            ConnectionModel.contact_id == contact_id,
        ),
        select(OAuthStateModel.id).where(
            OAuthStateModel.organization_id == organization_id,
            OAuthStateModel.contact_id == contact_id,
        ),
        select(CampaignContactModel.id).where(
            CampaignContactModel.organization_id == organization_id,
            CampaignContactModel.contact_id == contact_id,
        ),
        select(EventOutboxModel.id).where(
            EventOutboxModel.organization_id == organization_id,
            EventOutboxModel.subject_type == CONTACT_SUBJECT_TYPE,
            EventOutboxModel.subject_id == contact_id,
        ),
        select(MemoryModel.id).where(
            MemoryModel.organization_id == organization_id,
            MemoryModel.contact_id == contact_id,
        ),
        select(MemoryChangeModel.id).where(
            MemoryChangeModel.organization_id == organization_id,
            MemoryChangeModel.contact_id == contact_id,
        ),
    )
    for check in checks:
        if await session.scalar(check) is not None:
            raise RuntimeError("Contact erasure left a contact-owned row.")

    if user_session_ids:
        session_checks = (
            select(UserSessionModel.id).where(
                UserSessionModel.organization_id == organization_id,
                UserSessionModel.id.in_(user_session_ids),
            ),
            select(UserSessionConversationModel.id).where(
                UserSessionConversationModel.organization_id == organization_id,
                UserSessionConversationModel.user_session_id.in_(user_session_ids),
            ),
            select(MessagesModel.id).where(
                MessagesModel.user_session_id.in_(user_session_ids)
            ),
            select(AgentRunModel.id).where(
                AgentRunModel.organization_id == organization_id,
                AgentRunModel.user_session_id.in_(user_session_ids),
            ),
            select(VoiceSessionModel.id).where(
                VoiceSessionModel.organization_id == organization_id,
                VoiceSessionModel.user_session_id.in_(user_session_ids),
            ),
            select(TelephonyCallModel.id).where(
                TelephonyCallModel.organization_id == organization_id,
                TelephonyCallModel.user_session_id.in_(user_session_ids),
            ),
            select(KnowledgeIngestionJobModel.id).where(
                KnowledgeIngestionJobModel.organization_id == organization_id,
                KnowledgeIngestionJobModel.user_session_id.in_(user_session_ids),
            ),
            select(EventOutboxModel.id).where(
                EventOutboxModel.organization_id == organization_id,
                EventOutboxModel.correlation_id.in_(user_session_ids),
            ),
        )
        for check in session_checks:
            if await session.scalar(check) is not None:
                raise RuntimeError("Contact erasure left a user-session reference.")

    participant_reference = await session.scalar(
        select(ParticipantsModel.id)
        .join(
            ConversationsModel,
            ConversationsModel.id == ParticipantsModel.conversation_id,
        )
        .where(
            ConversationsModel.organization_id == organization_id,
            or_(
                ParticipantsModel.entity_id == contact_reference,
                ParticipantsModel.added_by_id == contact_reference,
                ParticipantsModel.removed_by_id == contact_reference,
            ),
        )
    )
    if participant_reference is not None:
        raise RuntimeError("Contact erasure left a participant reference.")
    if campaign_contact_ids:
        call_reference = await session.scalar(
            select(TelephonyCallModel.id).where(
                TelephonyCallModel.organization_id == organization_id,
                TelephonyCallModel.campaign_contact_id.in_(campaign_contact_ids),
            )
        )
        if call_reference is not None:
            raise RuntimeError("Contact erasure left a campaign-contact reference.")
    if attempt_ids:
        attempt_reference = await session.scalar(
            select(TelephonyCallModel.id).where(
                TelephonyCallModel.organization_id == organization_id,
                TelephonyCallModel.campaign_attempt_id.in_(attempt_ids),
            )
        )
        if attempt_reference is not None:
            raise RuntimeError("Contact erasure left a campaign-attempt reference.")


__all__ = ["ContactErasure", "erase_contact"]
