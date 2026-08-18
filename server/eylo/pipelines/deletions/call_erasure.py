"""Object-first erasure for one organization-owned telephony call root."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from absurd_sdk import AsyncTaskContext
from sqlalchemy import and_, delete, or_, select, update

from eylo.absurd_work import TERMINAL_STATES, DurableState
from eylo.common.contracts.memory import MemoryLevel, MemoryScope
from eylo.common.contracts.storage import StorageLocator
from eylo.common.database import start_transaction
from eylo.common.outbound import OutboundOwnerKind
from eylo.events.durable.models import EventOutboxModel
from eylo.events.durable.voice_contracts import (
    VOICE_MESSAGE_SUBJECT_TYPE,
    VOICE_RECORDING_SUBJECT_TYPE,
    VOICE_SESSION_SUBJECT_TYPE,
)
from eylo.modules.agent_runs.models import (
    AgentRunModel,
    OrganizationExecutionReservationModel,
)
from eylo.modules.auth.models import AuthSessionModel
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.deletions.domain import (
    DeletionErrorCode,
    DeletionExecutionFailure,
)
from eylo.modules.memory.models import (
    MemoryFormationCursorModel,
    MemoryFormationEffectModel,
    MemoryFormationJobModel,
    MemoryReconciliationJobModel,
)
from eylo.modules.telephony.lifecycle import (
    CALL_SUBJECT_TYPE,
    is_terminal_call_status,
)
from eylo.modules.telephony.models import TelephonyCallModel
from eylo.modules.voice.recording.model import VoiceRecordingModel
from eylo.modules.voice.recording.service import locator_from_recording
from eylo.modules.voice_transcripts.models import VoiceSegmentModel, VoiceSessionModel
from eylo.pipelines.deletions.memory_erasure import (
    MemoryOwnerGraphChanged,
    erase_memory_owner,
)
from eylo.pipelines.outbound.models import OutboundAttemptModel
from eylo.pipelines.storage.runtime import resolve_storage_runtime_pinned
from eylo.pipelines.voice.recording_storage import delete_recording_object
from eylo.products.campaigns.models import CampaignAttemptModel, CampaignContactModel

CALL_POLL_SECONDS = 30.0
WORK_POLL_SECONDS = 5.0

_DeleteObject = Callable[[StorageLocator], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class _BoundWork:
    state: DurableState


@dataclass(frozen=True, slots=True)
class _RecordingObjects:
    recording_id: UUID
    locators: tuple[StorageLocator, ...]


class _OwnershipConflict(Exception):
    """The persisted graph is not exclusively owned by the requested call."""


class _CallGraphChanged(Exception):
    """Call-owned work appeared or changed while erasure was being prepared."""


class CallErasure:
    """Quiesce writers, remove objects, then erase the exact DB graph."""

    def __init__(
        self,
        *,
        delete_object: _DeleteObject = delete_recording_object,
    ) -> None:
        self._delete_object = delete_object

    async def execute(
        self,
        *,
        organization_id: UUID,
        call_id: UUID,
        task_context: AsyncTaskContext,
    ) -> None:
        if not await _wait_for_terminal_call(
            organization_id=organization_id,
            call_id=call_id,
            task_context=task_context,
        ):
            return

        graph_wait_number = 0
        while True:
            await self._wait_for_call_work(
                organization_id=organization_id,
                call_id=call_id,
                task_context=task_context,
            )
            try:
                objects = await _load_recording_objects(
                    organization_id=organization_id,
                    call_id=call_id,
                )
            except Exception as error:
                raise DeletionExecutionFailure(
                    DeletionErrorCode.OBJECT_DELETE_FAILED,
                    retryable=True,
                ) from error

            await self._delete_recording_objects(objects)
            try:
                await _erase_call_graph(
                    organization_id=organization_id,
                    call_id=call_id,
                    object_deleted_recording_ids={
                        target.recording_id for target in objects
                    },
                )
            except _CallGraphChanged:
                graph_wait_number += 1
                await task_context.sleep_for(
                    f"wait-call-graph-stable-{graph_wait_number}",
                    WORK_POLL_SECONDS,
                )
                continue
            except MemoryOwnerGraphChanged:
                graph_wait_number += 1
                await task_context.sleep_for(
                    f"wait-call-memory-stable-{graph_wait_number}",
                    WORK_POLL_SECONDS,
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

    async def _wait_for_call_work(
        self,
        *,
        organization_id: UUID,
        call_id: UUID,
        task_context: AsyncTaskContext,
    ) -> None:
        wait_number = 0
        while True:
            try:
                recordings, memory_jobs = await _load_bound_work(
                    organization_id=organization_id,
                    call_id=call_id,
                )
            except Exception as error:
                raise DeletionExecutionFailure(
                    DeletionErrorCode.DEPENDENCY_UNAVAILABLE,
                    retryable=True,
                ) from error
            if all(
                work.state in TERMINAL_STATES for work in (*recordings, *memory_jobs)
            ):
                return
            wait_number += 1
            await task_context.sleep_for(
                f"wait-call-owned-work-{wait_number}",
                WORK_POLL_SECONDS,
            )

    async def _delete_recording_objects(
        self,
        targets: tuple[_RecordingObjects, ...],
    ) -> None:
        for target in targets:
            for locator in target.locators:
                try:
                    deleted = await self._delete_object(locator)
                except Exception as error:
                    raise DeletionExecutionFailure(
                        DeletionErrorCode.OBJECT_DELETE_FAILED,
                        retryable=True,
                    ) from error
                if not deleted:
                    raise DeletionExecutionFailure(
                        DeletionErrorCode.OBJECT_DELETE_FAILED,
                        retryable=True,
                    )


async def erase_call(
    *,
    organization_id: UUID,
    call_id: UUID,
    task_context: AsyncTaskContext,
) -> None:
    await CallErasure().execute(
        organization_id=organization_id,
        call_id=call_id,
        task_context=task_context,
    )


async def _wait_for_terminal_call(
    *,
    organization_id: UUID,
    call_id: UUID,
    task_context: AsyncTaskContext,
) -> bool:
    wait_number = 0
    while True:
        async with start_transaction(ro=True) as session:
            status = await session.scalar(
                select(TelephonyCallModel.status).where(
                    TelephonyCallModel.id == call_id,
                    TelephonyCallModel.organization_id == organization_id,
                )
            )
        if status is None:
            return False
        if is_terminal_call_status(status):
            return True
        wait_number += 1
        await task_context.sleep_for(
            f"wait-call-terminal-{wait_number}",
            CALL_POLL_SECONDS,
        )


async def _load_bound_work(
    *,
    organization_id: UUID,
    call_id: UUID,
) -> tuple[tuple[_BoundWork, ...], tuple[_BoundWork, ...]]:
    async with start_transaction(ro=True) as session:
        call = await session.scalar(
            select(TelephonyCallModel).where(
                TelephonyCallModel.id == call_id,
                TelephonyCallModel.organization_id == organization_id,
            )
        )
        if call is None:
            return (), ()
        recordings = tuple(
            _BoundWork(row.state)
            for row in (
                await session.scalars(
                    select(VoiceRecordingModel).where(
                        VoiceRecordingModel.organization_id == organization_id,
                        or_(
                            VoiceRecordingModel.telephony_call_id == call_id,
                            and_(
                                call.conversation_id is not None,
                                VoiceRecordingModel.conversation_id
                                == call.conversation_id,
                            ),
                        ),
                    )
                )
            ).all()
        )
        if call.conversation_id is None:
            return recordings, ()
        memory_jobs = tuple(
            _BoundWork(row.state)
            for row in (
                await session.scalars(
                    select(MemoryFormationJobModel).where(
                        MemoryFormationJobModel.organization_id == organization_id,
                        MemoryFormationJobModel.conversation_id == call.conversation_id,
                    )
                )
            ).all()
        )
        reconciliation_jobs = tuple(
            _BoundWork(row.state)
            for row in (
                await session.scalars(
                    select(MemoryReconciliationJobModel).where(
                        MemoryReconciliationJobModel.organization_id
                        == organization_id,
                        MemoryReconciliationJobModel.conversation_id
                        == call.conversation_id,
                    )
                )
            ).all()
        )
        return recordings, (*memory_jobs, *reconciliation_jobs)


async def _load_recording_objects(
    *,
    organization_id: UUID,
    call_id: UUID,
) -> tuple[_RecordingObjects, ...]:
    async with start_transaction(ro=True) as session:
        call = await session.scalar(
            select(TelephonyCallModel).where(
                TelephonyCallModel.id == call_id,
                TelephonyCallModel.organization_id == organization_id,
            )
        )
        if call is None:
            return ()
        rows = tuple(
            (
                await session.scalars(
                    select(VoiceRecordingModel)
                    .where(
                        VoiceRecordingModel.organization_id == organization_id,
                        or_(
                            VoiceRecordingModel.telephony_call_id == call_id,
                            and_(
                                call.conversation_id is not None,
                                VoiceRecordingModel.conversation_id
                                == call.conversation_id,
                            ),
                        ),
                    )
                    .order_by(VoiceRecordingModel.id)
                )
            ).all()
        )
    targets = []
    for recording in rows:
        locators = await _recording_locators(recording)
        targets.append(_RecordingObjects(recording.id, locators))
    return tuple(targets)


async def _recording_locators(
    recording: VoiceRecordingModel,
) -> tuple[StorageLocator, ...]:
    locators = [
        locator
        for track in ("user", "agent")
        if (locator := locator_from_recording(recording, track=track)) is not None
    ]
    final_by_key = {locator.key: locator for locator in locators}
    target_keys = tuple(
        key
        for key in (
            recording.target_user_storage_key,
            recording.target_agent_storage_key,
        )
        if key is not None
    )
    locators.extend(final_by_key[key] for key in target_keys if key in final_by_key)
    unresolved_target_keys = tuple(
        key for key in target_keys if key not in final_by_key
    )
    if unresolved_target_keys:
        if (
            recording.storage_provider_config_id is None
            or recording.storage_provider_config_revision is None
        ):
            raise ValueError("A staged recording is missing pinned storage authority.")
        async with start_transaction(ro=True) as session:
            runtime = await resolve_storage_runtime_pinned(
                recording.organization_id,
                provider_config_id=recording.storage_provider_config_id,
                revision=recording.storage_provider_config_revision,
                db=session,
            )
        locators.extend(runtime.locate(key) for key in unresolved_target_keys)
    by_uri = {locator.uri: locator for locator in locators}
    return tuple(by_uri[uri] for uri in sorted(by_uri))


async def _erase_call_graph(
    *,
    organization_id: UUID,
    call_id: UUID,
    object_deleted_recording_ids: set[UUID],
) -> None:
    async with start_transaction() as session:
        call = await session.scalar(
            select(TelephonyCallModel)
            .where(
                TelephonyCallModel.id == call_id,
                TelephonyCallModel.organization_id == organization_id,
            )
            .with_for_update()
        )
        if call is None:
            return
        if not is_terminal_call_status(call.status):
            raise _CallGraphChanged

        conversation_id = call.conversation_id
        sessions = tuple(
            (
                await session.scalars(
                    select(VoiceSessionModel)
                    .where(
                        VoiceSessionModel.organization_id == organization_id,
                        or_(
                            VoiceSessionModel.telephony_call_id == call_id,
                            and_(
                                conversation_id is not None,
                                VoiceSessionModel.conversation_id == conversation_id,
                            ),
                        ),
                    )
                    .with_for_update()
                )
            ).all()
        )
        recordings = tuple(
            (
                await session.scalars(
                    select(VoiceRecordingModel)
                    .where(
                        VoiceRecordingModel.organization_id == organization_id,
                        or_(
                            VoiceRecordingModel.telephony_call_id == call_id,
                            and_(
                                conversation_id is not None,
                                VoiceRecordingModel.conversation_id == conversation_id,
                            ),
                        ),
                    )
                    .with_for_update()
                )
            ).all()
        )
        _require_exclusive_ownership(
            call=call,
            sessions=sessions,
            recordings=recordings,
        )
        if {recording.id for recording in recordings} != object_deleted_recording_ids:
            raise _CallGraphChanged
        if any(recording.state not in TERMINAL_STATES for recording in recordings):
            raise _CallGraphChanged

        session_ids = {row.id for row in sessions}
        session_tokens = {row.session_id for row in sessions}
        recording_ids = {row.id for row in recordings}
        message_ids: set[UUID] = set()
        memory_job_ids: set[UUID] = set()

        if conversation_id is not None:
            conversation = await session.scalar(
                select(ConversationsModel)
                .where(
                    ConversationsModel.id == conversation_id,
                    ConversationsModel.organization_id == organization_id,
                )
                .with_for_update()
            )
            if conversation is None:
                raise _OwnershipConflict
            other_call = await session.scalar(
                select(TelephonyCallModel.id)
                .where(
                    TelephonyCallModel.organization_id == organization_id,
                    TelephonyCallModel.conversation_id == conversation_id,
                    TelephonyCallModel.id != call_id,
                )
                .with_for_update()
            )
            if other_call is not None:
                raise _OwnershipConflict
            messages = tuple(
                (
                    await session.scalars(
                        select(MessagesModel)
                        .where(MessagesModel.conversation_id == conversation_id)
                        .with_for_update()
                    )
                ).all()
            )
            message_ids = {message.id for message in messages}
            if any(message.agent_run_id is not None for message in messages):
                raise _OwnershipConflict
            if message_ids:
                run = await session.scalar(
                    select(AgentRunModel.id).where(
                        AgentRunModel.organization_id == organization_id,
                        AgentRunModel.origin_message_id.in_(message_ids),
                    )
                )
                if run is not None:
                    raise _OwnershipConflict
            memory_jobs = tuple(
                (
                    await session.scalars(
                        select(MemoryFormationJobModel)
                        .where(
                            MemoryFormationJobModel.organization_id == organization_id,
                            MemoryFormationJobModel.conversation_id == conversation_id,
                        )
                        .with_for_update()
                    )
                ).all()
            )
            if any(job.state not in TERMINAL_STATES for job in memory_jobs):
                raise _CallGraphChanged
            memory_job_ids = {job.id for job in memory_jobs}

        await _erase_event_facts(
            session,
            organization_id=organization_id,
            call_id=call_id,
            session_ids=session_ids,
            recording_ids=recording_ids,
            message_ids=message_ids,
        )
        await _erase_outbound_facts(
            session,
            organization_id=organization_id,
            call_id=call_id,
            recording_ids=recording_ids,
        )
        await _detach_campaign_tracking(session, call)

        call.voice_session_id = None
        await session.flush()

        if session_tokens:
            await session.execute(
                delete(AuthSessionModel).where(
                    AuthSessionModel.organization_id == organization_id,
                    AuthSessionModel.session_token.in_(session_tokens),
                )
            )
        if memory_job_ids:
            await session.execute(
                delete(OrganizationExecutionReservationModel).where(
                    OrganizationExecutionReservationModel.organization_id
                    == organization_id,
                    OrganizationExecutionReservationModel.memory_formation_job_id.in_(
                        memory_job_ids
                    ),
                )
            )
            await session.execute(
                delete(MemoryFormationEffectModel).where(
                    MemoryFormationEffectModel.organization_id == organization_id,
                    MemoryFormationEffectModel.formation_job_id.in_(memory_job_ids),
                )
            )
        if conversation_id is not None:
            await session.execute(
                delete(MemoryFormationCursorModel).where(
                    MemoryFormationCursorModel.organization_id == organization_id,
                    MemoryFormationCursorModel.conversation_id == conversation_id,
                )
            )
            await erase_memory_owner(
                session,
                MemoryScope(
                    organization_id=organization_id,
                    level=MemoryLevel.CONVERSATION,
                    owner_id=conversation_id,
                ),
            )
            await session.execute(
                delete(MemoryFormationJobModel).where(
                    MemoryFormationJobModel.organization_id == organization_id,
                    MemoryFormationJobModel.conversation_id == conversation_id,
                )
            )

        if session_ids:
            await session.execute(
                delete(VoiceSegmentModel).where(
                    VoiceSegmentModel.voice_session_id.in_(session_ids)
                )
            )
        if recording_ids:
            await session.execute(
                delete(VoiceRecordingModel).where(
                    VoiceRecordingModel.organization_id == organization_id,
                    VoiceRecordingModel.id.in_(recording_ids),
                )
            )
        if session_ids:
            await session.execute(
                delete(VoiceSessionModel).where(
                    VoiceSessionModel.organization_id == organization_id,
                    VoiceSessionModel.id.in_(session_ids),
                )
            )
        await session.execute(
            delete(TelephonyCallModel).where(
                TelephonyCallModel.organization_id == organization_id,
                TelephonyCallModel.id == call_id,
            )
        )

        if conversation_id is not None:
            await session.execute(
                delete(MessagesModel).where(
                    MessagesModel.conversation_id == conversation_id
                )
            )
            await session.execute(
                delete(ParticipantsModel).where(
                    ParticipantsModel.conversation_id == conversation_id
                )
            )
            await session.execute(
                delete(ConversationsModel).where(
                    ConversationsModel.id == conversation_id,
                    ConversationsModel.organization_id == organization_id,
                )
            )
        await session.flush()
        await _require_call_graph_absent(
            session,
            organization_id=organization_id,
            call_id=call_id,
            conversation_id=conversation_id,
            session_ids=session_ids,
            recording_ids=recording_ids,
        )


def _require_exclusive_ownership(
    *,
    call: TelephonyCallModel,
    sessions: tuple[VoiceSessionModel, ...],
    recordings: tuple[VoiceRecordingModel, ...],
) -> None:
    conversation_id = call.conversation_id
    if conversation_id is None and (sessions or recordings):
        raise _OwnershipConflict
    if any(
        row.telephony_call_id != call.id
        or row.conversation_id != conversation_id
        or row.organization_id != call.organization_id
        for row in sessions
    ):
        raise _OwnershipConflict
    session_owners = {row.id: row.session_id for row in sessions}
    if any(
        row.telephony_call_id != call.id
        or row.conversation_id != conversation_id
        or row.organization_id != call.organization_id
        or session_owners.get(row.voice_session_id) != row.session_id
        for row in recordings
    ):
        raise _OwnershipConflict
    if (
        call.voice_session_id is not None
        and call.voice_session_id not in session_owners
    ):
        raise _OwnershipConflict


async def _erase_event_facts(
    session,
    *,
    organization_id: UUID,
    call_id: UUID,
    session_ids: set[UUID],
    recording_ids: set[UUID],
    message_ids: set[UUID],
) -> None:
    owned = [
        and_(
            EventOutboxModel.subject_type == CALL_SUBJECT_TYPE,
            EventOutboxModel.subject_id == call_id,
        )
    ]
    if session_ids:
        owned.extend(
            [
                and_(
                    EventOutboxModel.subject_type == VOICE_SESSION_SUBJECT_TYPE,
                    EventOutboxModel.subject_id.in_(session_ids),
                ),
                EventOutboxModel.correlation_id.in_(session_ids),
            ]
        )
    if recording_ids:
        owned.append(
            and_(
                EventOutboxModel.subject_type == VOICE_RECORDING_SUBJECT_TYPE,
                EventOutboxModel.subject_id.in_(recording_ids),
            )
        )
    if message_ids:
        owned.append(
            and_(
                EventOutboxModel.subject_type == VOICE_MESSAGE_SUBJECT_TYPE,
                EventOutboxModel.subject_id.in_(message_ids),
            )
        )
    await session.execute(
        delete(EventOutboxModel).where(
            EventOutboxModel.organization_id == organization_id,
            or_(*owned),
        )
    )


async def _erase_outbound_facts(
    session,
    *,
    organization_id: UUID,
    call_id: UUID,
    recording_ids: set[UUID],
) -> None:
    owned = [
        and_(
            OutboundAttemptModel.owner_kind == OutboundOwnerKind.TELEPHONY_CALL,
            OutboundAttemptModel.owner_id == call_id,
        )
    ]
    if recording_ids:
        owned.append(
            and_(
                OutboundAttemptModel.owner_kind == OutboundOwnerKind.VOICE_RECORDING,
                OutboundAttemptModel.owner_id.in_(recording_ids),
            )
        )
    await session.execute(
        delete(OutboundAttemptModel).where(
            OutboundAttemptModel.organization_id == organization_id,
            or_(*owned),
        )
    )


async def _detach_campaign_tracking(session, call: TelephonyCallModel) -> None:
    tracking_ids = {str(call.id)}
    if call.call_sid is not None:
        tracking_ids.add(call.call_sid)
    if call.campaign_attempt_id is not None:
        await session.execute(
            update(CampaignAttemptModel)
            .where(
                CampaignAttemptModel.id == call.campaign_attempt_id,
                CampaignAttemptModel.organization_id == call.organization_id,
                CampaignAttemptModel.tracking_id.in_(tracking_ids),
            )
            .values(tracking_id=None)
        )
    if call.campaign_contact_id is not None:
        await session.execute(
            update(CampaignContactModel)
            .where(
                CampaignContactModel.id == call.campaign_contact_id,
                CampaignContactModel.organization_id == call.organization_id,
                CampaignContactModel.last_tracking_id.in_(tracking_ids),
            )
            .values(last_tracking_id=None)
        )


async def _require_call_graph_absent(
    session,
    *,
    organization_id: UUID,
    call_id: UUID,
    conversation_id: UUID | None,
    session_ids: set[UUID],
    recording_ids: set[UUID],
) -> None:
    remaining = await session.scalar(
        select(TelephonyCallModel.id).where(
            TelephonyCallModel.organization_id == organization_id,
            TelephonyCallModel.id == call_id,
        )
    )
    if remaining is not None:
        raise RuntimeError("Call erasure did not remove its root.")
    if conversation_id is not None:
        remaining = await session.scalar(
            select(ConversationsModel.id).where(
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.id == conversation_id,
            )
        )
        if remaining is not None:
            raise RuntimeError("Call erasure did not remove its conversation.")
    if session_ids:
        remaining = await session.scalar(
            select(VoiceSessionModel.id).where(
                VoiceSessionModel.organization_id == organization_id,
                VoiceSessionModel.id.in_(session_ids),
            )
        )
        if remaining is not None:
            raise RuntimeError("Call erasure did not remove every voice session.")
    if recording_ids:
        remaining = await session.scalar(
            select(VoiceRecordingModel.id).where(
                VoiceRecordingModel.organization_id == organization_id,
                VoiceRecordingModel.id.in_(recording_ids),
            )
        )
        if remaining is not None:
            raise RuntimeError("Call erasure did not remove every recording row.")


__all__ = ["CallErasure", "erase_call"]
