"""Absurd workflow for durable voice-recording uploads."""

from __future__ import annotations

import logging
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from absurd_sdk import AsyncTaskContext, CancelledTask
from sqlalchemy import select

from eylo.absurd_work import (
    AbsurdBoundWorkService,
    DurableState,
    DurableWorkBindingPending,
    DurableWorkNotFound,
    spawn_bound_work,
    spawn_unbound_work,
)
from eylo.common.contracts.storage import StorageAuthority, StorageLocator
from eylo.common.database import start_transaction
from eylo.common.identifiers import as_stdlib_uuid
from eylo.common.outbound import OutboundAttemptState
from eylo.durable_runtime import PlatformDurableRuntime
from eylo.events.durable.binding import spawn_event_deliveries
from eylo.events.durable.domain import DurableEventEnvelope
from eylo.events.durable.service import DurableEventService
from eylo.events.durable.voice_contracts import (
    VOICE_RECORDING_ATTACHMENT_CONSUMER,
    VOICE_RECORDING_AVAILABLE_EVENT_TYPE,
    VOICE_RECORDING_AVAILABLE_EVENT_VERSION,
    VOICE_RECORDING_SUBJECT_TYPE,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.voice.recording.model import VoiceRecordingModel
from eylo.modules.voice_transcripts.models import VoiceSessionModel
from eylo.pipelines.storage.runtime import resolve_storage_runtime_pinned
from eylo.pipelines.voice.recording_outbound import (
    RecordingAbsurdStepContext,
    cancel_recording_upload_attempts,
    execute_recording_track_upload,
)

logger = logging.getLogger(__name__)

VOICE_RECORDING_UPLOAD_WORKFLOW = "eylo.voice.recording.upload.v1"


class RecordingUploadContractError(Exception):
    """Persisted recording work is incomplete and cannot succeed on retry."""


class RecordingUploadUnconfirmed(Exception):
    """A stable-key PUT may exist and must not be replayed blindly."""


class RecordingUploadRejected(Exception):
    """A stable-key PUT reached a terminal provider outcome."""


def register_voice_recording_upload_workflow(
    runtime: PlatformDurableRuntime,
) -> None:
    workflow = VoiceRecordingUploadWorkflow()
    runtime.register_task(
        name=VOICE_RECORDING_UPLOAD_WORKFLOW,
        handler=workflow.execute,
    )


async def spawn_voice_recording_upload(
    *,
    organization_id: UUID,
    recording_id: UUID,
) -> UUID:
    return await spawn_bound_work(
        model=VoiceRecordingModel,
        organization_id=organization_id,
        work_id=recording_id,
        workflow_name=VOICE_RECORDING_UPLOAD_WORKFLOW,
        params_name="recording_id",
        idempotency_prefix="voice-recording-upload",
    )


async def spawn_unbound_voice_recording_uploads(*, limit: int = 100) -> int:
    async def spawn(organization_id: UUID, recording_id: UUID) -> UUID:
        return await spawn_voice_recording_upload(
            organization_id=organization_id,
            recording_id=recording_id,
        )

    spawned, failures = await spawn_unbound_work(
        model=VoiceRecordingModel,
        spawn=spawn,
        limit=limit,
    )
    for recording_id, error in failures:
        logger.error(
            "Could not spawn recording upload %s. error_type=%s",
            recording_id,
            type(error).__name__,
        )
    return spawned


class VoiceRecordingUploadWorkflow:
    """Upload stable track keys while the DB row remains product authority."""

    async def execute(
        self,
        params: dict[str, Any],
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        organization_id, recording_id = _parse_params(params)
        try:
            return await self._execute(
                organization_id=organization_id,
                recording_id=recording_id,
                task_context=task_context,
            )
        except DurableWorkNotFound:
            return {
                "organization_id": str(organization_id),
                "recording_id": str(recording_id),
                "state": "deleted",
            }
        except CancelledTask as cancelled:
            try:
                required_track_count = await _required_track_count(
                    organization_id=organization_id,
                    recording_id=recording_id,
                )
            except DurableWorkNotFound:
                raise cancelled
            try:
                cancellation = await cancel_recording_upload_attempts(
                    organization_id=organization_id,
                    recording_id=recording_id,
                    required_track_count=required_track_count,
                )
            except Exception as error:  # noqa: BLE001 - preserve data on uncertainty
                logger.error(
                    "Could not fence recording upload attempts: %s",
                    type(error).__name__,
                )
                cancellation = None

            if cancellation is not None and cancellation.all_required_succeeded:
                try:
                    recording_event_id = await _project_succeeded_targets(
                        organization_id=organization_id,
                        recording_id=recording_id,
                    )
                except Exception as error:  # noqa: BLE001 - ledger remains authority
                    logger.error(
                        "Could not project accepted recording upload: %s",
                        type(error).__name__,
                    )
                else:
                    await _nudge_recording_available_fact(
                        organization_id=organization_id,
                        event_id=recording_event_id,
                    )
                    raise cancelled

            async with start_transaction() as session:
                try:
                    row = await AbsurdBoundWorkService(
                        VoiceRecordingModel,
                        session,
                    ).get(
                        work_id=recording_id,
                        organization_id=organization_id,
                        for_update=True,
                    )
                except DurableWorkNotFound:
                    raise cancelled
                await AbsurdBoundWorkService(
                    VoiceRecordingModel,
                    session,
                ).cancel(
                    work_id=recording_id,
                    organization_id=organization_id,
                )
                if cancellation is None or cancellation.may_have_external_effect:
                    _preserve_staged_audio(
                        row,
                        state=DurableState.CANCELLED,
                        effect_state="accepted_or_unknown",
                    )
                else:
                    _discard_staged_audio(row, state=DurableState.CANCELLED)
            raise

    async def _execute(
        self,
        *,
        organization_id: UUID,
        recording_id: UUID,
        task_context: AsyncTaskContext,
    ) -> dict[str, Any]:
        terminal_receipt: dict[str, Any] | None = None
        recording_event_id: UUID | None = None
        try:
            async with start_transaction() as session:
                row = await AbsurdBoundWorkService(
                    VoiceRecordingModel,
                    session,
                ).begin_attempt(
                    work_id=recording_id,
                    organization_id=organization_id,
                )
                if row.state in {
                    DurableState.SUCCEEDED,
                    DurableState.FAILED,
                    DurableState.CANCELLED,
                }:
                    if row.state is DurableState.SUCCEEDED:
                        recording_event_id = await _file_recording_available_fact(
                            session,
                            row,
                        )
                    terminal_receipt = _receipt(row)
                else:
                    provider_config_id = row.storage_provider_config_id
                    provider_config_revision = row.storage_provider_config_revision
                    user_wav = row.staged_user_wav
                    agent_wav = row.staged_agent_wav
                    user_key = row.target_user_storage_key
                    agent_key = row.target_agent_storage_key
        except DurableWorkBindingPending:
            raise
        except Exception as error:  # noqa: BLE001 - load failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                recording_id=recording_id,
                error=error,
                permanent=_is_permanent(error),
            )

        if terminal_receipt is not None:
            if recording_event_id is not None:
                await _nudge_recording_available_fact(
                    organization_id=organization_id,
                    event_id=recording_event_id,
                )
            return terminal_receipt

        if provider_config_id is None or provider_config_revision is None:
            return await _handle_failure(
                organization_id=organization_id,
                recording_id=recording_id,
                error=RecordingUploadContractError(
                    "Recording upload has no exact storage config revision."
                ),
                permanent=True,
            )
        if user_wav is None and agent_wav is None:
            return await _handle_failure(
                organization_id=organization_id,
                recording_id=recording_id,
                error=RecordingUploadContractError(
                    "Recording upload has no staged audio."
                ),
                permanent=True,
            )

        try:
            async with start_transaction(ro=True) as session:
                storage = await resolve_storage_runtime_pinned(
                    organization_id,
                    provider_config_id=provider_config_id,
                    revision=provider_config_revision,
                    db=session,
                )
        except Exception as error:  # noqa: BLE001 - resolution is product state
            return await _handle_failure(
                organization_id=organization_id,
                recording_id=recording_id,
                error=error,
                permanent=_is_permanent(error),
            )

        try:
            user_locator, agent_locator = await _upload_tracks(
                organization_id=organization_id,
                recording_id=recording_id,
                storage=storage,
                task_context=task_context,
                user_wav=user_wav,
                agent_wav=agent_wav,
                user_key=user_key,
                agent_key=agent_key,
            )
            authority = _shared_authority(user_locator, agent_locator)
        except Exception as error:  # noqa: BLE001 - provider failure is product state
            return await _handle_failure(
                organization_id=organization_id,
                recording_id=recording_id,
                error=error,
                permanent=_is_permanent(error),
                preserve_staged=True,
            )

        row, recording_event_id = await _project_recording_success(
            organization_id=organization_id,
            recording_id=recording_id,
            user_locator=user_locator,
            agent_locator=agent_locator,
            authority=authority,
        )

        await _nudge_recording_available_fact(
            organization_id=organization_id,
            event_id=recording_event_id,
        )
        return _receipt(row)


async def _upload_tracks(
    *,
    organization_id: UUID,
    recording_id: UUID,
    storage,
    task_context: AsyncTaskContext,
    user_wav: bytes | None,
    agent_wav: bytes | None,
    user_key: str | None,
    agent_key: str | None,
) -> tuple[StorageLocator | None, StorageLocator | None]:
    if user_wav is not None and user_key is None:
        raise RecordingUploadContractError("User recording has no stable target key.")
    if agent_wav is not None and agent_key is None:
        raise RecordingUploadContractError("Agent recording has no stable target key.")

    context = RecordingAbsurdStepContext(task_context)
    user_locator = None
    agent_locator = None
    for track, content, key in (
        ("user", user_wav, user_key),
        ("agent", agent_wav, agent_key),
    ):
        if content is None:
            continue
        result = await execute_recording_track_upload(
            organization_id=organization_id,
            recording_id=recording_id,
            track=track,
            content=content,
            key=key,
            storage=storage,
            context=context,
        )
        if result.receipt.state is OutboundAttemptState.UNKNOWN:
            raise RecordingUploadUnconfirmed(
                f"{track} recording upload requires storage reconciliation."
            )
        if result.receipt.state is not OutboundAttemptState.SUCCEEDED:
            raise RecordingUploadRejected(
                f"{track} recording upload ended as {result.receipt.state.value}."
            )
        if track == "user":
            user_locator = result.locator
        else:
            agent_locator = result.locator
    return user_locator, agent_locator


async def _project_recording_success(
    *,
    organization_id: UUID,
    recording_id: UUID,
    user_locator: StorageLocator | None,
    agent_locator: StorageLocator | None,
    authority: StorageAuthority,
) -> tuple[VoiceRecordingModel, UUID]:
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(VoiceRecordingModel, session)
        current = await service.get(
            work_id=recording_id,
            organization_id=organization_id,
            for_update=True,
        )
        if current.state is DurableState.SUCCEEDED:
            return current, await _file_recording_available_fact(session, current)
        meta = {**(current.meta or {}), "upload_state": DurableState.SUCCEEDED.value}
        meta.pop("upload_error", None)
        meta.pop("upload_effect_state", None)
        row = await service.succeed(
            work_id=recording_id,
            organization_id=organization_id,
            values={
                "user_audio_url": None,
                "agent_audio_url": None,
                "storage_provider": authority.provider,
                "storage_authority": dict(authority.location),
                "user_storage_key": user_locator.key if user_locator else None,
                "agent_storage_key": agent_locator.key if agent_locator else None,
                "staged_user_wav": None,
                "staged_agent_wav": None,
                "meta": meta,
            },
        )
        return row, await _file_recording_available_fact(session, row)


async def _project_succeeded_targets(
    *,
    organization_id: UUID,
    recording_id: UUID,
) -> UUID:
    async with start_transaction(ro=True) as session:
        row = await AbsurdBoundWorkService(VoiceRecordingModel, session).get(
            work_id=recording_id,
            organization_id=organization_id,
        )
        provider_config_id = row.storage_provider_config_id
        provider_config_revision = row.storage_provider_config_revision
        user_key = (
            row.target_user_storage_key if row.staged_user_wav is not None else None
        )
        agent_key = (
            row.target_agent_storage_key if row.staged_agent_wav is not None else None
        )
    if provider_config_id is None or provider_config_revision is None:
        raise RecordingUploadContractError(
            "Accepted recording upload has no exact storage config revision."
        )
    async with start_transaction(ro=True) as session:
        storage = await resolve_storage_runtime_pinned(
            organization_id,
            provider_config_id=provider_config_id,
            revision=provider_config_revision,
            db=session,
        )
    user_locator = storage.locate(user_key) if user_key is not None else None
    agent_locator = storage.locate(agent_key) if agent_key is not None else None
    _, event_id = await _project_recording_success(
        organization_id=organization_id,
        recording_id=recording_id,
        user_locator=user_locator,
        agent_locator=agent_locator,
        authority=_shared_authority(user_locator, agent_locator),
    )
    return event_id


async def _required_track_count(
    *,
    organization_id: UUID,
    recording_id: UUID,
) -> int:
    async with start_transaction(ro=True) as session:
        row = await AbsurdBoundWorkService(VoiceRecordingModel, session).get(
            work_id=recording_id,
            organization_id=organization_id,
        )
        return sum(
            content is not None
            for content in (row.staged_user_wav, row.staged_agent_wav)
        )


async def _handle_failure(
    *,
    organization_id: UUID,
    recording_id: UUID,
    error: Exception,
    permanent: bool,
    preserve_staged: bool = False,
) -> dict[str, Any]:
    summary = _safe_failure_summary(error)
    async with start_transaction() as session:
        service = AbsurdBoundWorkService(VoiceRecordingModel, session)
        state = await service.fail(
            work_id=recording_id,
            organization_id=organization_id,
            error=summary,
            permanent=permanent,
        )
        row = await service.get(
            work_id=recording_id,
            organization_id=organization_id,
            for_update=True,
        )
        if state is DurableState.FAILED:
            if preserve_staged:
                _preserve_staged_audio(
                    row,
                    state=state,
                    error=summary,
                    effect_state=(
                        "unknown"
                        if isinstance(error, RecordingUploadUnconfirmed)
                        else (
                            "terminal"
                            if isinstance(error, RecordingUploadRejected)
                            else "incomplete"
                        )
                    ),
                )
            else:
                _discard_staged_audio(row, state=state, error=summary)
            voice_session = await session.scalar(
                select(VoiceSessionModel)
                .where(
                    VoiceSessionModel.organization_id == organization_id,
                    VoiceSessionModel.session_id == row.session_id,
                )
                .with_for_update()
            )
            if voice_session is not None:
                voice_session.meta = {
                    **(voice_session.meta or {}),
                    "recording_upload_error": summary[:2000],
                }
                if voice_session.user_session_id is not None:
                    await file_user_session_fact(
                        session,
                        organization_id=organization_id,
                        user_session_id=voice_session.user_session_id,
                        subject_type=VOICE_RECORDING_SUBJECT_TYPE,
                        subject_id=recording_id,
                        event_type="voice.recording.failed",
                        payload={
                            "conversation_id": str(row.conversation_id),
                            "voice_session_id": str(voice_session.id),
                            "reason": "upload_failed",
                        },
                    )
    if state is DurableState.PENDING:
        raise error
    logger.warning(
        "Voice recording upload %s failed. error_type=%s",
        recording_id,
        type(error).__name__,
    )
    return {
        "organization_id": str(organization_id),
        "recording_id": str(recording_id),
        "state": state.value,
    }


def _discard_staged_audio(
    row: VoiceRecordingModel,
    *,
    state: DurableState,
    error: str | None = None,
) -> None:
    row.staged_user_wav = None
    row.staged_agent_wav = None
    meta = {**(row.meta or {}), "upload_state": state.value}
    if error is not None:
        meta["upload_error"] = error[:2000]
    row.meta = meta


def _preserve_staged_audio(
    row: VoiceRecordingModel,
    *,
    state: DurableState,
    effect_state: str,
    error: str | None = None,
) -> None:
    meta = {
        **(row.meta or {}),
        "upload_state": state.value,
        "upload_effect_state": effect_state,
    }
    if error is not None:
        meta["upload_error"] = error[:2000]
    row.meta = meta


def _is_permanent(error: Exception) -> bool:
    return isinstance(
        error,
        (
            NotConfiguredError,
            RecordingUploadContractError,
            RecordingUploadRejected,
        ),
    )


def _safe_failure_summary(error: Exception) -> str:
    """Return an operator-visible failure without provider exception content."""
    if isinstance(error, NotConfiguredError):
        return "Recording storage is not configured."
    if isinstance(error, RecordingUploadContractError):
        return "Recording upload data is incomplete."
    if isinstance(error, RecordingUploadUnconfirmed):
        return "Recording upload outcome could not be confirmed."
    if isinstance(error, RecordingUploadRejected):
        return "Recording storage rejected the upload."
    return "Recording upload failed."


def _parse_params(params: dict[str, Any]) -> tuple[UUID, UUID]:
    if set(params) != {"organization_id", "recording_id"}:
        raise ValueError("Recording upload task params must contain IDs only.")
    try:
        return UUID(str(params["organization_id"])), UUID(str(params["recording_id"]))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Recording upload task params contain an invalid UUID."
        ) from error


def _shared_authority(
    user_locator: StorageLocator | None,
    agent_locator: StorageLocator | None,
) -> StorageAuthority:
    locators = [locator for locator in (user_locator, agent_locator) if locator]
    if not locators:
        raise RecordingUploadContractError("Recording upload produced no locator.")
    authority = locators[0].authority
    if any(locator.authority != authority for locator in locators[1:]):
        raise RecordingUploadContractError(
            "Recording tracks resolved through different storage authority."
        )
    return authority


async def _file_recording_available_fact(session, row: VoiceRecordingModel) -> UUID:
    if row.state is not DurableState.SUCCEEDED or row.finished_at is None:
        raise RecordingUploadContractError(
            "Recording availability requires a successful canonical upload."
        )
    organization_id = as_stdlib_uuid(row.organization_id)
    recording_id = as_stdlib_uuid(row.id)
    voice_session = await session.scalar(
        select(VoiceSessionModel).where(
            VoiceSessionModel.id == row.voice_session_id,
            VoiceSessionModel.organization_id == organization_id,
            VoiceSessionModel.conversation_id == row.conversation_id,
            VoiceSessionModel.session_id == row.session_id,
            VoiceSessionModel.deleted.is_(False),
        )
    )
    if voice_session is None:
        raise RecordingUploadContractError(
            "Recording availability has no exact voice-session authority."
        )
    event_id = uuid5(
        NAMESPACE_URL,
        f"eylo:{VOICE_RECORDING_AVAILABLE_EVENT_TYPE}:v1:"
        f"{organization_id}:{recording_id}",
    )
    await DurableEventService(session).file(
        envelope=DurableEventEnvelope(
            event_id=event_id,
            organization_id=organization_id,
            subject_type=VOICE_RECORDING_SUBJECT_TYPE,
            subject_id=recording_id,
            event_type=VOICE_RECORDING_AVAILABLE_EVENT_TYPE,
            event_version=VOICE_RECORDING_AVAILABLE_EVENT_VERSION,
            occurred_at=row.finished_at,
            recorded_at=row.finished_at,
            correlation_id=(
                as_stdlib_uuid(voice_session.user_session_id)
                if voice_session.user_session_id is not None
                else None
            ),
            payload={
                "conversation_id": str(row.conversation_id),
                "voice_session_id": str(voice_session.id),
            },
        ),
        consumer_names=(VOICE_RECORDING_ATTACHMENT_CONSUMER,),
    )
    return event_id


async def _nudge_recording_available_fact(
    *,
    organization_id: UUID,
    event_id: UUID,
) -> None:
    try:
        spawned = await spawn_event_deliveries(
            organization_id=organization_id,
            event_id=event_id,
        )
    except Exception as error:  # noqa: BLE001 - periodic recovery owns binding
        logger.error(
            "Could not nudge recording fact %s. error_type=%s",
            event_id,
            type(error).__name__,
        )
        return
    for delivery_id, _summary in spawned.failures:
        logger.error(
            "Could not nudge recording delivery %s.",
            delivery_id,
        )


def _receipt(row: VoiceRecordingModel) -> dict[str, Any]:
    return {
        "organization_id": str(row.organization_id),
        "recording_id": str(row.id),
        "state": row.state.value,
    }


__all__ = [
    "VOICE_RECORDING_UPLOAD_WORKFLOW",
    "VoiceRecordingUploadWorkflow",
    "register_voice_recording_upload_workflow",
    "spawn_unbound_voice_recording_uploads",
    "spawn_voice_recording_upload",
]
