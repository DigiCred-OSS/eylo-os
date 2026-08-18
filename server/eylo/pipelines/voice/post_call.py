"""Destructive in-process projection of raw live voice state after a call."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select

from eylo.common.contracts.voice import (
    VOICE_MESSAGE_META_REDACTION_VERSION,
    VOICE_MESSAGE_META_RUNTIME_MODE,
    VOICE_MESSAGE_META_SESSION_ID,
    VOICE_MESSAGE_META_SESSION_ROW_ID,
    VOICE_MESSAGE_META_SOURCE_SEQUENCE,
    VOICE_MESSAGE_META_SPEECH_OUTCOME,
)
from eylo.common.database import start_transaction
from eylo.common.redaction import redact_value
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.message_content import (
    AssistantMessageContent,
    TextContent,
    ToolResultContent,
    ToolResultMessageContent,
    ToolUseContent,
    ToolUseMessageContent,
    UserMessageContent,
)
from eylo.modules.conversations.schemas.messages import (
    MessageContentKind,
    MessageCreate,
    MessageInDb,
    MessageKind,
    MessageMeta,
    RequestStatus,
)
from eylo.modules.conversations.schemas.participants import ParticipantKind
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.voice_transcripts.constants import (
    VOICE_CANONICAL_REDACTION_VERSION,
    VoiceAudioTrackKind,
    VoiceCanonicalState,
    VoiceRuntimeMode,
    VoiceSegmentRole,
    VoiceSegmentSource,
    VoiceSegmentType,
    VoiceSpeechOutcome,
)
from eylo.modules.voice_transcripts.models import VoiceSessionModel
from eylo.modules.voice_transcripts.schemas.indb import (
    VoiceSegmentCreate,
    VoiceSessionInDb,
)
from eylo.modules.voice_transcripts.services.indb import VoiceTranscriptService
from eylo.pipelines.voice.live_buffer import (
    LiveVoiceBuffer,
    LiveVoiceBufferFailure,
    LiveVoiceBufferIdentity,
    LiveVoiceBufferSnapshot,
    LiveVoiceItem,
    LiveVoiceItemKind,
)
from eylo.pipelines.voice.request_state import VoiceRequestSource

logger = logging.getLogger(__name__)

_TERMINAL_STATES = frozenset(
    {
        VoiceCanonicalState.CLEAN,
        VoiceCanonicalState.REDACTED,
        VoiceCanonicalState.FAILED,
        VoiceCanonicalState.NO_STORAGE,
    }
)


class VoiceProjectionAuthorityError(Exception):
    """The live buffer cannot resolve its exact tenant/session authority."""


class VoiceProjectionBuildError(Exception):
    """Canonical history cannot be built from otherwise valid session state."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("Canonical voice history input is unavailable.")


@dataclass(frozen=True, slots=True)
class VoiceProjectionResult:
    voice_session_id: UUID
    state: VoiceCanonicalState
    message_count: int
    segment_count: int
    source_complete: bool | None
    failure_code: str | None
    replayed: bool


@dataclass(frozen=True, slots=True)
class _CanonicalItem:
    sequence: int
    kind: LiveVoiceItemKind
    payload: str | dict[str, Any]
    changed: bool
    occurred_at: datetime
    participant_id: UUID | None
    request_id: UUID | None
    tool_call_id: str | None
    tool_name: str | None
    is_error: bool | None
    speech_outcome: str | None
    policy_source: VoiceRequestSource | None


@dataclass(frozen=True, slots=True)
class _ParticipantAuthority:
    contact_id: UUID | None
    agent_id: UUID | None


async def finalize_live_voice_history(
    live_buffer: LiveVoiceBuffer,
) -> VoiceProjectionResult:
    """Seal raw memory and synchronously write only its redacted projection."""
    return await project_live_voice_snapshot(await live_buffer.seal())


async def project_live_voice_snapshot(
    snapshot: LiveVoiceBufferSnapshot,
) -> VoiceProjectionResult:
    """Project one sealed snapshot without placing raw content in durable work."""
    session = await _load_exact_session(snapshot.identity)
    existing = _existing_result(session)
    if existing is not None:
        return existing

    try:
        storage_requested = _storage_decision(session, snapshot.identity)
    except VoiceProjectionBuildError as error:
        return await _record_terminal_state(
            snapshot.identity,
            state=VoiceCanonicalState.FAILED,
            source_complete=snapshot.complete,
            failure_code=error.code,
            redaction_version=VOICE_CANONICAL_REDACTION_VERSION,
        )

    if not storage_requested:
        return await _record_terminal_state(
            snapshot.identity,
            state=VoiceCanonicalState.NO_STORAGE,
            source_complete=snapshot.complete,
            failure_code=None,
            redaction_version=None,
        )
    if not snapshot.complete:
        return await _record_terminal_state(
            snapshot.identity,
            state=VoiceCanonicalState.FAILED,
            source_complete=False,
            failure_code=_source_failure_code(snapshot.failure),
            redaction_version=VOICE_CANONICAL_REDACTION_VERSION,
        )

    try:
        items = _redact_items(snapshot.items)
    except Exception as error:  # noqa: BLE001 - raw value must never enter logs
        logger.error(
            "Post-call voice redaction failed error_type=%s",
            type(error).__name__,
        )
        return await _record_terminal_state(
            snapshot.identity,
            state=VoiceCanonicalState.FAILED,
            source_complete=True,
            failure_code="redaction_failed",
            redaction_version=VOICE_CANONICAL_REDACTION_VERSION,
        )

    state = (
        VoiceCanonicalState.REDACTED
        if any(item.changed for item in items)
        else VoiceCanonicalState.CLEAN
    )
    try:
        return await _persist_projection(snapshot.identity, items, state=state)
    except VoiceProjectionAuthorityError:
        raise
    except VoiceProjectionBuildError as error:
        failure_code = error.code
    except Exception as error:  # noqa: BLE001 - transaction rollback owns content
        logger.error(
            "Post-call voice projection failed error_type=%s",
            type(error).__name__,
        )
        failure_code = "projection_failed"
    return await _record_terminal_state(
        snapshot.identity,
        state=VoiceCanonicalState.FAILED,
        source_complete=True,
        failure_code=failure_code,
        redaction_version=VOICE_CANONICAL_REDACTION_VERSION,
    )


async def _load_exact_session(identity: LiveVoiceBufferIdentity) -> VoiceSessionInDb:
    if identity.voice_session_id is None:
        raise VoiceProjectionAuthorityError
    async with start_transaction(ro=True) as db:
        row = await db.scalar(
            select(VoiceSessionModel).where(
                VoiceSessionModel.id == identity.voice_session_id,
                VoiceSessionModel.organization_id == identity.organization_id,
                VoiceSessionModel.deleted.is_(False),
            )
        )
        session = VoiceSessionInDb.model_validate(row) if row is not None else None
    if session is None:
        raise VoiceProjectionAuthorityError
    _validate_identity(session, identity)
    return session


def _validate_identity(
    session: VoiceSessionInDb | VoiceSessionModel,
    identity: LiveVoiceBufferIdentity,
) -> None:
    if (
        session.id != identity.voice_session_id
        or session.organization_id != identity.organization_id
        or session.conversation_id != identity.conversation_id
        or session.session_id != identity.session_id
        or VoiceRuntimeMode(session.runtime_mode) is not identity.runtime_mode
    ):
        raise VoiceProjectionAuthorityError


def _storage_decision(
    session: VoiceSessionInDb,
    identity: LiveVoiceBufferIdentity,
) -> bool:
    meta = session.meta
    if (
        not isinstance(meta, dict)
        or "canonical_storage_requested" not in meta
        or not isinstance(meta["canonical_storage_requested"], bool)
    ):
        raise VoiceProjectionBuildError("storage_decision_unavailable")
    requested = meta["canonical_storage_requested"]
    if requested is not identity.canonical_storage_requested:
        raise VoiceProjectionBuildError("storage_decision_conflict")
    return requested


def _existing_result(session: VoiceSessionInDb) -> VoiceProjectionResult | None:
    state = VoiceCanonicalState(session.canonical_state)
    if state not in _TERMINAL_STATES:
        return None
    return VoiceProjectionResult(
        voice_session_id=session.id,
        state=state,
        message_count=session.canonical_message_count,
        segment_count=session.segment_count,
        source_complete=session.canonical_source_complete,
        failure_code=session.canonical_failure_code,
        replayed=True,
    )


def _redact_items(items: tuple[LiveVoiceItem, ...]) -> tuple[_CanonicalItem, ...]:
    redacted: list[_CanonicalItem] = []
    expected_sequence = 1
    for item in items:
        if item.sequence != expected_sequence:
            raise VoiceProjectionBuildError("source_order_invalid")
        payload = redact_value(item.payload)
        if not isinstance(payload, (str, dict)):
            raise VoiceProjectionBuildError("redacted_payload_invalid")
        redacted.append(
            _CanonicalItem(
                sequence=item.sequence,
                kind=item.kind,
                payload=payload,
                changed=payload != item.payload,
                occurred_at=item.occurred_at,
                participant_id=item.participant_id,
                request_id=item.request_id,
                tool_call_id=item.tool_call_id,
                tool_name=item.tool_name,
                is_error=item.is_error,
                speech_outcome=item.speech_outcome,
                policy_source=item.policy_source,
            )
        )
        expected_sequence += 1
    return tuple(redacted)


async def _persist_projection(
    identity: LiveVoiceBufferIdentity,
    items: tuple[_CanonicalItem, ...],
    *,
    state: VoiceCanonicalState,
) -> VoiceProjectionResult:
    async with start_transaction() as db:
        session_row = await db.scalar(
            select(VoiceSessionModel)
            .where(
                VoiceSessionModel.id == identity.voice_session_id,
                VoiceSessionModel.organization_id == identity.organization_id,
                VoiceSessionModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if session_row is None:
            raise VoiceProjectionAuthorityError
        _validate_identity(session_row, identity)
        existing = _existing_result(VoiceSessionInDb.model_validate(session_row))
        if existing is not None:
            return existing
        if not _storage_decision(
            VoiceSessionInDb.model_validate(session_row),
            identity,
        ):
            raise VoiceProjectionBuildError("storage_decision_conflict")

        participants = await _participant_authority(db, session_row, items)
        message_service = MessageService(db)
        transcript_service = VoiceTranscriptService(db)
        voice_session = VoiceSessionInDb.model_validate(session_row)
        message_count = 0
        for item in items:
            message = None
            if item.kind is not LiveVoiceItemKind.SYSTEM_SPEECH:
                message = await message_service.create_canonical_projection(
                    organization_id=identity.organization_id,
                    message=_message_create(identity, participants, item),
                )
                message_count += 1
            await transcript_service.create_projected_segment(
                voice_session=voice_session,
                data=_segment_create(identity, message, item),
            )
        await transcript_service.refresh_session_rollups(session_row.id)
        session_row.canonical_state = state
        session_row.canonical_redaction_version = VOICE_CANONICAL_REDACTION_VERSION
        session_row.canonical_failure_code = None
        session_row.canonical_source_complete = True
        session_row.canonical_projected_at = datetime.now(timezone.utc)
        session_row.canonical_message_count = message_count
        await db.flush()
        segment_count = await transcript_service.count_segments(session_row.id)

    return VoiceProjectionResult(
        voice_session_id=identity.voice_session_id,
        state=state,
        message_count=message_count,
        segment_count=segment_count,
        source_complete=True,
        failure_code=None,
        replayed=False,
    )


async def _participant_authority(
    db,
    session: VoiceSessionModel,
    items: tuple[_CanonicalItem, ...],
) -> _ParticipantAuthority:
    rows = list(
        (
            await db.scalars(
                select(ParticipantsModel).where(
                    ParticipantsModel.conversation_id == session.conversation_id,
                    ParticipantsModel.deleted.is_(False),
                    ParticipantsModel.is_active.is_(True),
                    ParticipantsModel.is_primary.is_(True),
                )
            )
        ).all()
    )
    needs_contact = any(
        item.kind in {LiveVoiceItemKind.USER_TRANSCRIPT, LiveVoiceItemKind.DTMF}
        for item in items
    )
    needs_agent = any(
        item.kind
        in {
            LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
            LiveVoiceItemKind.TOOL_CALL,
            LiveVoiceItemKind.TOOL_RESULT,
        }
        for item in items
    )
    contacts = [row for row in rows if row.entity_kind == ParticipantKind.CONTACT.value]
    agents = [
        row
        for row in rows
        if row.entity_kind == ParticipantKind.AGENT.value
        and row.agent_id == session.agent_id
        and row.agent_revision == session.agent_revision
    ]
    if (needs_contact and len(contacts) != 1) or (needs_agent and len(agents) != 1):
        raise VoiceProjectionBuildError("participant_authority_unavailable")
    contact_id = contacts[0].id if contacts else None
    agent_id = agents[0].id if agents else None
    for item in items:
        if item.kind is LiveVoiceItemKind.SYSTEM_SPEECH:
            expected = None
        elif item.kind in {
            LiveVoiceItemKind.USER_TRANSCRIPT,
            LiveVoiceItemKind.DTMF,
        }:
            expected = contact_id
        else:
            expected = agent_id
        if item.participant_id is not None and item.participant_id != expected:
            raise VoiceProjectionBuildError("participant_authority_conflict")
    return _ParticipantAuthority(contact_id=contact_id, agent_id=agent_id)


def _message_create(
    identity: LiveVoiceBufferIdentity,
    participants: _ParticipantAuthority,
    item: _CanonicalItem,
) -> MessageCreate:
    sender_id = (
        participants.contact_id
        if item.kind in {LiveVoiceItemKind.USER_TRANSCRIPT, LiveVoiceItemKind.DTMF}
        else participants.agent_id
    )
    if sender_id is None:
        raise VoiceProjectionBuildError("participant_authority_unavailable")
    request_id = _request_id(identity, item)
    kind, content_kind, content, status = _message_content(item)
    meta: dict[str, Any] = {
        VOICE_MESSAGE_META_SESSION_ID: identity.session_id,
        VOICE_MESSAGE_META_SESSION_ROW_ID: str(identity.voice_session_id),
        VOICE_MESSAGE_META_RUNTIME_MODE: identity.runtime_mode.value,
        VOICE_MESSAGE_META_SOURCE_SEQUENCE: item.sequence,
        VOICE_MESSAGE_META_REDACTION_VERSION: VOICE_CANONICAL_REDACTION_VERSION,
        "source": "realtime"
        if identity.runtime_mode is VoiceRuntimeMode.BROWSER_REALTIME
        else "voice",
    }
    if item.speech_outcome is not None:
        meta[VOICE_MESSAGE_META_SPEECH_OUTCOME] = item.speech_outcome
    return MessageCreate(
        conversation_id=identity.conversation_id,
        sender_participant_id=sender_id,
        created_at=item.occurred_at,
        kind=kind,
        content_kind=content_kind,
        content=content,
        request_id=request_id,
        request_status=status,
        meta=MessageMeta.model_validate(meta),
        external_id=f"voice:{identity.voice_session_id}:{item.sequence}",
    )


def _message_content(
    item: _CanonicalItem,
) -> tuple[MessageKind, MessageContentKind, object, RequestStatus]:
    if item.kind is LiveVoiceItemKind.USER_TRANSCRIPT:
        text = _text_payload(item)
        return (
            MessageKind.USER,
            MessageContentKind.TEXT,
            UserMessageContent(content=[TextContent(text=text)]),
            RequestStatus.COMPLETED,
        )
    if item.kind is LiveVoiceItemKind.DTMF:
        text = f"DTMF digits: {_text_payload(item)}"
        return (
            MessageKind.USER,
            MessageContentKind.TEXT,
            UserMessageContent(content=[TextContent(text=text)]),
            RequestStatus.COMPLETED,
        )
    if item.kind is LiveVoiceItemKind.ASSISTANT_TRANSCRIPT:
        outcome = _speech_outcome(item)
        return (
            MessageKind.ASSISTANT,
            MessageContentKind.TEXT,
            AssistantMessageContent(content=[TextContent(text=_text_payload(item))]),
            _speech_request_status(outcome),
        )
    if item.kind is LiveVoiceItemKind.TOOL_CALL:
        if (
            not isinstance(item.payload, dict)
            or not item.tool_call_id
            or not item.tool_name
        ):
            raise VoiceProjectionBuildError("tool_call_invalid")
        return (
            MessageKind.TOOL_USE,
            MessageContentKind.TOOL,
            ToolUseMessageContent(
                content=ToolUseContent(
                    id=item.tool_call_id,
                    name=item.tool_name,
                    input=item.payload,
                )
            ),
            RequestStatus.COMPLETED,
        )
    if not item.tool_call_id:
        raise VoiceProjectionBuildError("tool_result_invalid")
    return (
        MessageKind.TOOL_RESULT,
        MessageContentKind.TOOL,
        ToolResultMessageContent(
            content=[
                ToolResultContent(
                    tool_use_id=item.tool_call_id,
                    name=item.tool_name,
                    content=item.payload,
                    is_error=bool(item.is_error),
                )
            ]
        ),
        RequestStatus.FAILED if item.is_error else RequestStatus.COMPLETED,
    )


def _segment_create(
    identity: LiveVoiceBufferIdentity,
    message: MessageInDb | None,
    item: _CanonicalItem,
) -> VoiceSegmentCreate:
    role, segment_type, source, audio_track = _segment_class(identity, item)
    text = None
    tool_input = None
    tool_output = None
    dtmf_digits = None
    if item.kind is LiveVoiceItemKind.SYSTEM_SPEECH:
        text = _text_payload(item)
    elif item.kind in {
        LiveVoiceItemKind.USER_TRANSCRIPT,
        LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
    }:
        if message is None:
            raise VoiceProjectionBuildError("message_projection_unavailable")
        text = MessageService.get_message_content(message.content)
    elif item.kind is LiveVoiceItemKind.DTMF:
        dtmf_digits = _text_payload(item)
    elif item.kind is LiveVoiceItemKind.TOOL_CALL:
        tool_input = item.payload if isinstance(item.payload, dict) else None
    elif item.kind is LiveVoiceItemKind.TOOL_RESULT:
        tool_output = {
            "content": item.payload,
            "is_error": bool(item.is_error),
        }
    return VoiceSegmentCreate(
        organization_id=identity.organization_id,
        voice_session_id=identity.voice_session_id,
        conversation_id=identity.conversation_id,
        message_id=message.id if message is not None else None,
        request_id=(
            message.request_id
            if message is not None
            else _request_id(identity, item)
        ),
        source_created_at=item.occurred_at,
        sequence=item.sequence - 1,
        role=role,
        segment_type=segment_type,
        source=source,
        speech_outcome=(
            _speech_outcome(item)
            if item.kind
            in {
                LiveVoiceItemKind.ASSISTANT_TRANSCRIPT,
                LiveVoiceItemKind.SYSTEM_SPEECH,
            }
            else None
        ),
        text=text,
        audio_track=audio_track,
        tool_name=item.tool_name,
        tool_call_id=item.tool_call_id,
        tool_input=tool_input,
        tool_output=tool_output,
        dtmf_digits=dtmf_digits,
        redaction_state="redacted" if item.changed else "clean",
        meta={
            "source_sequence": item.sequence,
            "redaction_version": VOICE_CANONICAL_REDACTION_VERSION,
            **(
                {"policy_source": item.policy_source.value}
                if item.policy_source is not None
                else {}
            ),
        },
    )


def _segment_class(
    identity: LiveVoiceBufferIdentity,
    item: _CanonicalItem,
) -> tuple[
    VoiceSegmentRole,
    VoiceSegmentType,
    VoiceSegmentSource,
    VoiceAudioTrackKind | None,
]:
    if item.kind is LiveVoiceItemKind.USER_TRANSCRIPT:
        return (
            VoiceSegmentRole.USER,
            VoiceSegmentType.SPEECH,
            VoiceSegmentSource.REALTIME
            if identity.runtime_mode is VoiceRuntimeMode.BROWSER_REALTIME
            else VoiceSegmentSource.STT,
            VoiceAudioTrackKind.USER,
        )
    if item.kind is LiveVoiceItemKind.ASSISTANT_TRANSCRIPT:
        return (
            VoiceSegmentRole.ASSISTANT,
            VoiceSegmentType.SPEECH,
            VoiceSegmentSource.REALTIME
            if identity.runtime_mode is VoiceRuntimeMode.BROWSER_REALTIME
            else VoiceSegmentSource.TTS,
            VoiceAudioTrackKind.ASSISTANT,
        )
    if item.kind is LiveVoiceItemKind.SYSTEM_SPEECH:
        if item.policy_source is None:
            raise VoiceProjectionBuildError("policy_source_unavailable")
        return (
            VoiceSegmentRole.SYSTEM,
            VoiceSegmentType.SPEECH,
            VoiceSegmentSource.SYSTEM,
            VoiceAudioTrackKind.ASSISTANT,
        )
    if item.kind is LiveVoiceItemKind.DTMF:
        return (
            VoiceSegmentRole.USER,
            VoiceSegmentType.EVENT,
            VoiceSegmentSource.TELEPHONY,
            VoiceAudioTrackKind.USER,
        )
    return (
        VoiceSegmentRole.TOOL,
        VoiceSegmentType.TOOL_CALL
        if item.kind is LiveVoiceItemKind.TOOL_CALL
        else VoiceSegmentType.TOOL_RESULT,
        VoiceSegmentSource.TOOL,
        None,
    )


def _text_payload(item: _CanonicalItem) -> str:
    if not isinstance(item.payload, str):
        raise VoiceProjectionBuildError("text_payload_invalid")
    return item.payload


def _request_id(
    identity: LiveVoiceBufferIdentity,
    item: _CanonicalItem,
) -> UUID:
    return item.request_id or uuid5(
        NAMESPACE_URL,
        f"eylo:voice-request:{identity.organization_id}:"
        f"{identity.voice_session_id}:{item.sequence}",
    )


def _speech_outcome(item: _CanonicalItem) -> VoiceSpeechOutcome:
    try:
        return VoiceSpeechOutcome(str(item.speech_outcome))
    except ValueError as error:
        raise VoiceProjectionBuildError(
            "assistant_speech_outcome_unavailable"
        ) from error


def _speech_request_status(outcome: VoiceSpeechOutcome) -> RequestStatus:
    return {
        VoiceSpeechOutcome.DRAINED: RequestStatus.COMPLETED,
        VoiceSpeechOutcome.INTERRUPTED: RequestStatus.INTERRUPTED,
        VoiceSpeechOutcome.FAILED: RequestStatus.FAILED,
        VoiceSpeechOutcome.CANCELLED: RequestStatus.SKIPPED,
    }[outcome]


async def _record_terminal_state(
    identity: LiveVoiceBufferIdentity,
    *,
    state: VoiceCanonicalState,
    source_complete: bool,
    failure_code: str | None,
    redaction_version: int | None,
) -> VoiceProjectionResult:
    async with start_transaction() as db:
        session = await db.scalar(
            select(VoiceSessionModel)
            .where(
                VoiceSessionModel.id == identity.voice_session_id,
                VoiceSessionModel.organization_id == identity.organization_id,
                VoiceSessionModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if session is None:
            raise VoiceProjectionAuthorityError
        _validate_identity(session, identity)
        existing = _existing_result(VoiceSessionInDb.model_validate(session))
        if existing is not None:
            return existing
        session.canonical_state = state
        session.canonical_redaction_version = redaction_version
        session.canonical_failure_code = failure_code
        session.canonical_source_complete = source_complete
        session.canonical_projected_at = datetime.now(timezone.utc)
        session.canonical_message_count = 0
        await db.flush()
        segment_count = await VoiceTranscriptService(db).count_segments(session.id)

    return VoiceProjectionResult(
        voice_session_id=identity.voice_session_id,
        state=state,
        message_count=0,
        segment_count=segment_count,
        source_complete=source_complete,
        failure_code=failure_code,
        replayed=False,
    )


def _source_failure_code(failure: LiveVoiceBufferFailure | None) -> str:
    return {
        LiveVoiceBufferFailure.CAPACITY_EXCEEDED: "source_capacity_exceeded",
        LiveVoiceBufferFailure.INVALID_PAYLOAD: "source_invalid_payload",
    }.get(failure, "source_capture_incomplete")


__all__ = [
    "VoiceProjectionAuthorityError",
    "VoiceProjectionResult",
    "finalize_live_voice_history",
    "project_live_voice_snapshot",
]
