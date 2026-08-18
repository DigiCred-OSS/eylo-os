"""Service layer for voice transcript session and segment orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import arrow
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.redaction import redact, redact_value
from eylo.common.services import EyloBaseService
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.schemas.messages import (
    MessageInDb,
    MessageKind,
    RequestStatus,
)
from eylo.modules.conversations.services.messages import MessageService
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.voice_transcripts.constants import (
    VoiceAudioTrackKind,
    VoiceRuntimeMode,
    VoiceSegmentRole,
    VoiceSegmentSource,
    VoiceSegmentType,
    VoiceSessionStatus,
    VoiceSpeechOutcome,
)
from eylo.modules.voice_transcripts.repositories import (
    VoiceSegmentRepository,
    VoiceSessionRepository,
)
from eylo.modules.voice_transcripts.schemas.indb import (
    VoiceSegmentCreate,
    VoiceSegmentInDb,
    VoiceSessionCreate,
    VoiceSessionInDb,
    VoiceSessionUpdate,
)


class VoiceTranscriptService(EyloBaseService[VoiceSessionInDb]):
    """Business operations for voice transcript sessions and segments."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._repository = VoiceSessionRepository(db)
        self.segments = VoiceSegmentRepository(db)

    @property
    def schema(self) -> type[VoiceSessionInDb]:
        return VoiceSessionInDb

    @property
    def repository(self) -> VoiceSessionRepository:
        return self._repository

    async def start_session(self, data: VoiceSessionCreate) -> VoiceSessionInDb:
        """Atomically create or resolve one exact active runtime session."""
        conversation_organization_id = await self.repository.db_session.scalar(
            select(ConversationsModel.organization_id).where(
                ConversationsModel.id == data.conversation_id,
                ConversationsModel.deleted.is_(False),
            )
        )
        if conversation_organization_id != data.organization_id:
            raise ValueError("Voice session conversation authority is unavailable.")
        existing = await self.repository.get_by_session_key(
            organization_id=data.organization_id,
            session_id=data.session_id,
            runtime_mode=data.runtime_mode.value,
        )
        if existing:
            return self._validate_idempotent_start(existing, data)

        try:
            async with self.repository.db_session.begin_nested():
                entity = await self.repository.create(data)
        except IntegrityError:
            existing = await self.repository.get_by_session_key(
                organization_id=data.organization_id,
                session_id=data.session_id,
                runtime_mode=data.runtime_mode.value,
            )
            if existing is None:
                raise
            return self._validate_idempotent_start(existing, data)
        created = self.orm_to_schema(entity)
        if created.user_session_id is not None:
            await file_user_session_fact(
                self.repository.db_session,
                organization_id=created.organization_id,
                user_session_id=created.user_session_id,
                subject_type="voice.session",
                subject_id=created.id,
                event_type="voice.session.started",
                occurred_at=created.started_at,
                payload={
                    "conversation_id": str(created.conversation_id),
                    "runtime_mode": created.runtime_mode.value,
                    "transport": created.transport,
                    "agent_id": str(created.agent_id) if created.agent_id else None,
                    "agent_revision": created.agent_revision,
                },
            )
        return created

    def _validate_idempotent_start(
        self,
        existing: Any,
        requested: VoiceSessionCreate,
    ) -> VoiceSessionInDb:
        """Return an exact active duplicate; reject reuse or authority drift."""
        if VoiceSessionStatus(existing.status) is not VoiceSessionStatus.ACTIVE:
            raise ValueError("A completed voice runtime session cannot be reopened.")

        authority_fields = (
            "conversation_id",
            "user_session_id",
            "transport",
            "agent_id",
            "agent_revision",
            "stt_vendor",
            "stt_model",
            "tts_vendor",
            "tts_model",
            "tts_voice",
            "realtime_vendor",
            "realtime_model",
            "telephony_call_id",
            "provider_call_id",
            "telephony_provider",
            "from_number",
            "to_number",
            "recording_enabled",
            "recording_consent",
            "audio_format",
            "meta",
        )
        if any(
            getattr(existing, field) != getattr(requested, field)
            for field in authority_fields
        ):
            raise ValueError(
                "Voice runtime session identity conflicts with canonical authority."
            )
        return self.orm_to_schema(existing)

    async def get_session(
        self, *, organization_id: UUID, session_id: UUID
    ) -> VoiceSessionInDb | None:
        entity = await self.repository.get_by_id(
            organization_id=organization_id, session_id=session_id
        )
        return self.orm_to_schema(entity) if entity else None

    async def get_by_conversation(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> VoiceSessionInDb | None:
        entity = await self.repository.get_by_conversation(
            organization_id=organization_id,
            conversation_id=conversation_id,
        )
        return self.orm_to_schema(entity) if entity else None

    async def list_sessions(
        self,
        *,
        organization_id: UUID,
        limit: int,
        offset: int,
        conversation_id: UUID | None = None,
        agent_id: UUID | None = None,
        status: VoiceSessionStatus | None = None,
        runtime_mode: VoiceRuntimeMode | None = None,
    ) -> list[VoiceSessionInDb]:
        entities = await self.repository.list_by_organization(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            conversation_id=conversation_id,
            agent_id=agent_id,
            status=status.value if status else None,
            runtime_mode=runtime_mode.value if runtime_mode else None,
        )
        return self.orm_to_schema_list(entities)

    async def count_sessions(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID | None = None,
        agent_id: UUID | None = None,
        status: VoiceSessionStatus | None = None,
        runtime_mode: VoiceRuntimeMode | None = None,
    ) -> int:
        return await self.repository.count_by_organization(
            organization_id=organization_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            status=status.value if status else None,
            runtime_mode=runtime_mode.value if runtime_mode else None,
        )

    async def create_segment(self, data: VoiceSegmentCreate) -> VoiceSegmentInDb:
        """Persist a voice transcript segment and update session counters."""
        voice_session = await self.repository.get_by_id(
            organization_id=data.organization_id,
            session_id=data.voice_session_id,
        )
        if (
            voice_session is None
            or voice_session.conversation_id != data.conversation_id
        ):
            raise ValueError("Voice segment session authority is unavailable.")
        data = self._apply_compliance(data, session_meta=voice_session.meta or {})
        entity = await self.segments.create(data)
        segment = VoiceSegmentInDb.model_validate(entity)
        await self.refresh_session_rollups(segment.voice_session_id)
        return segment

    async def create_projected_segment(
        self,
        *,
        voice_session: VoiceSessionInDb,
        data: VoiceSegmentCreate,
    ) -> VoiceSegmentInDb:
        """Persist one already-redacted child under exact session authority."""
        is_system_speech = (
            data.message_id is None
            and data.role is VoiceSegmentRole.SYSTEM
            and data.segment_type is VoiceSegmentType.SPEECH
            and data.source is VoiceSegmentSource.SYSTEM
            and data.request_id is not None
            and data.speech_outcome is not None
            and data.text is not None
            and data.audio_track is VoiceAudioTrackKind.ASSISTANT
        )
        if (
            data.sequence is None
            or data.organization_id != voice_session.organization_id
            or data.voice_session_id != voice_session.id
            or data.conversation_id != voice_session.conversation_id
            or (data.message_id is None and not is_system_speech)
            or data.redaction_state not in {"clean", "redacted"}
        ):
            raise ValueError("Canonical voice segment authority is invalid.")
        existing = (
            await self.segments.get_by_message_id(data.message_id)
            if data.message_id is not None
            else await self.segments.get_by_session_sequence(
                data.voice_session_id,
                data.sequence,
            )
        )
        if existing is not None:
            existing_projection = VoiceSegmentCreate.model_validate(
                VoiceSegmentInDb.model_validate(existing).model_dump()
            )
            if existing_projection != data:
                raise ValueError("Canonical voice segment identity conflicts.")
            return VoiceSegmentInDb.model_validate(existing)
        return VoiceSegmentInDb.model_validate(await self.segments.create(data))

    def _apply_compliance(
        self,
        data: VoiceSegmentCreate,
        *,
        session_meta: dict[str, Any],
    ) -> VoiceSegmentCreate:
        """Drop payloads the agent's CompliancePlan forbids storing.

        Enforced here because every segment — message-derived and explicitly
        captured — passes through `create_segment`. The session authority read
        also supplies the pinned compliance metadata, avoiding a separate
        agent-config query on this hot path.

        Stripping happens before the write. A segment persisted and redacted
        afterwards has still been persisted.
        """
        if not session_meta.get("store_raw_vendor_payloads", False):
            data = data.model_copy(update={"vendor_metadata": None})
        if not session_meta.get("allow_sensitive_metadata", False):
            data = data.model_copy(update={"meta": None})
        if session_meta.get("redact_pii_in_transcripts", False):
            data = self._redact_segment(data)
        return data

    @staticmethod
    def _redact_segment(data: VoiceSegmentCreate) -> VoiceSegmentCreate:
        """Replace shaped personal data everywhere a segment carries text."""
        redacted = {
            field: redact_value(getattr(data, field))
            for field in ("text", "tool_input", "tool_output")
        }
        redacted |= {
            field: redact(getattr(data, field))
            for field in ("dtmf_digits", "transfer_to", "error_message")
        }
        changed = any(
            value != getattr(data, field) for field, value in redacted.items()
        )
        if changed:
            redacted["words"] = None
        return data.model_copy(
            update=redacted | {"redaction_state": "redacted" if changed else "clean"}
        )

    async def create_segment_from_canonical_message(
        self,
        *,
        voice_session: VoiceSessionInDb,
        message: MessageInDb,
    ) -> VoiceSegmentInDb | None:
        """Project one canonical message once under exact session authority."""
        existing = await self.segments.get_by_message_id(message.id)
        if existing is not None:
            if (
                existing.organization_id != voice_session.organization_id
                or existing.voice_session_id != voice_session.id
                or existing.conversation_id != message.conversation_id
            ):
                raise ValueError(
                    "Canonical voice message is bound to another transcript authority."
                )
            return VoiceSegmentInDb.model_validate(existing)
        payload = self._segment_from_message(voice_session, message)
        if not payload:
            return None
        return await self.create_segment(payload)

    async def list_segments(
        self,
        voice_session_id: UUID,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[VoiceSegmentInDb]:
        if limit <= 0 or limit > 200 or offset < 0:
            raise ValueError("Voice segment pagination is outside its bounds.")
        entities = await self.segments.list_by_session(
            voice_session_id,
            limit=limit,
            offset=offset,
        )
        return [
            VoiceSegmentInDb.model_validate(entity).model_copy(
                update={"sequence": offset + sequence}
            )
            for sequence, entity in enumerate(entities)
        ]

    async def count_segments(self, voice_session_id: UUID) -> int:
        return await self.segments.count_by_session(voice_session_id)

    async def reconcile_completed_session(
        self,
        *,
        organization_id: UUID,
        voice_session_id: UUID,
    ) -> VoiceSessionInDb | None:
        """Recompute terminal rollups from canonical session and segment state."""
        entity = await self.repository.get_by_id(
            organization_id=organization_id,
            session_id=voice_session_id,
        )
        if (
            not entity
            or entity.status == VoiceSessionStatus.ACTIVE
            or entity.ended_at is None
        ):
            return None
        rollup = await self.segments.summarize(entity.id)
        silence_ms = None
        if (
            entity.duration_ms is not None
            and rollup.user_talk_time_ms is not None
            and rollup.assistant_talk_time_ms is not None
        ):
            silence_ms = max(
                entity.duration_ms
                - rollup.user_talk_time_ms
                - rollup.assistant_talk_time_ms,
                0,
            )

        updated = await self.repository.update(
            entity.id,
            VoiceSessionUpdate(
                segment_count=rollup.segment_count,
                partial_segment_count=rollup.partial_segment_count,
                user_talk_time_ms=rollup.user_talk_time_ms,
                assistant_talk_time_ms=rollup.assistant_talk_time_ms,
                silence_time_ms=silence_ms,
                interruption_count=rollup.interruption_count,
                dtmf_count=rollup.dtmf_count,
                transfer_count=rollup.transfer_count,
            ),
        )
        if not updated:
            return None
        return self.orm_to_schema(updated)

    async def update_audio_references(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        session_id: str,
        user_audio_url: str | None = None,
        assistant_audio_url: str | None = None,
        combined_audio_url: str | None = None,
        user_audio_recording_id: UUID | None = None,
        assistant_audio_recording_id: UUID | None = None,
        combined_audio_recording_id: UUID | None = None,
        audio_format: str | None = None,
    ) -> VoiceSessionInDb | None:
        """Attach recorder-produced audio storage references to a voice session."""
        session = await self.repository.get_by_conversation_session(
            organization_id=organization_id,
            conversation_id=conversation_id,
            session_id=session_id,
        )
        if (
            not session
            or session.organization_id != organization_id
            or session.session_id != session_id
        ):
            return None
        updated = await self.repository.update(
            session.id,
            VoiceSessionUpdate(
                user_audio_url=user_audio_url,
                assistant_audio_url=assistant_audio_url,
                combined_audio_url=combined_audio_url,
                user_audio_recording_id=user_audio_recording_id,
                assistant_audio_recording_id=assistant_audio_recording_id,
                combined_audio_recording_id=combined_audio_recording_id,
                audio_format=audio_format,
            ),
        )
        return self.orm_to_schema(updated) if updated else None

    async def refresh_session_rollups(self, voice_session_id: UUID) -> None:
        entity = await self.repository.get_(voice_session_id)
        if not entity:
            return

        rollup = await self.segments.summarize(voice_session_id)
        update_data = VoiceSessionUpdate(
            segment_count=rollup.segment_count,
            partial_segment_count=rollup.partial_segment_count,
            user_talk_time_ms=rollup.user_talk_time_ms,
            assistant_talk_time_ms=rollup.assistant_talk_time_ms,
            interruption_count=rollup.interruption_count,
            dtmf_count=rollup.dtmf_count,
            transfer_count=rollup.transfer_count,
        )
        if (
            entity.status == VoiceSessionStatus.COMPLETED
            and entity.duration_ms is not None
            and rollup.user_talk_time_ms is not None
            and rollup.assistant_talk_time_ms is not None
        ):
            update_data.silence_time_ms = max(
                entity.duration_ms
                - rollup.user_talk_time_ms
                - rollup.assistant_talk_time_ms,
                0,
            )
        await self.repository.update(voice_session_id, update_data)

    def _segment_from_message(
        self, session: VoiceSessionInDb, message: MessageInDb
    ) -> VoiceSegmentCreate | None:
        role, segment_type, source, audio_track = _classify_message(message)
        if not role:
            return None
        text = MessageService.get_message_content(message.content)
        started_at_ms = _duration_ms(session.started_at, message.created_at)
        duration_ms = None
        if message.meta and hasattr(message.meta, "get"):
            raw_duration = message.meta.get("duration_ms")
            duration_ms = int(raw_duration) if raw_duration is not None else None
        tool_name, tool_call_id, tool_input, tool_output = _extract_tool_fields(message)
        speech_outcome = (
            _speech_outcome(message) if role is VoiceSegmentRole.ASSISTANT else None
        )
        if role is VoiceSegmentRole.ASSISTANT and speech_outcome is None:
            raise ValueError("Assistant voice message has no terminal speech outcome.")
        return VoiceSegmentCreate(
            organization_id=session.organization_id,
            voice_session_id=session.id,
            conversation_id=message.conversation_id,
            message_id=message.id,
            request_id=message.request_id,
            source_created_at=message.created_at,
            role=role,
            segment_type=segment_type,
            source=source,
            speech_outcome=speech_outcome,
            text=text,
            started_at_ms=started_at_ms,
            duration_ms=duration_ms,
            audio_track=audio_track,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            tool_output=tool_output,
            meta={
                "message_kind": message.kind.value
                if hasattr(message.kind, "value")
                else str(message.kind)
            },
        )


def _classify_message(
    message: MessageInDb,
) -> tuple[
    VoiceSegmentRole | None,
    VoiceSegmentType,
    VoiceSegmentSource,
    VoiceAudioTrackKind | None,
]:
    meta_source = None
    if message.meta and hasattr(message.meta, "get"):
        meta_source = message.meta.get("source")
    source = (
        VoiceSegmentSource.REALTIME
        if meta_source == "realtime"
        else VoiceSegmentSource.MESSAGE
    )
    if message.kind == MessageKind.USER:
        return (
            VoiceSegmentRole.USER,
            VoiceSegmentType.SPEECH,
            source,
            VoiceAudioTrackKind.USER,
        )
    if message.kind == MessageKind.ASSISTANT:
        return (
            VoiceSegmentRole.ASSISTANT,
            VoiceSegmentType.SPEECH,
            source,
            VoiceAudioTrackKind.ASSISTANT,
        )
    if message.kind == MessageKind.TOOL_USE:
        return (
            VoiceSegmentRole.TOOL,
            VoiceSegmentType.TOOL_CALL,
            VoiceSegmentSource.TOOL,
            None,
        )
    return None, VoiceSegmentType.EVENT, VoiceSegmentSource.MESSAGE, None


def _speech_outcome(message: MessageInDb) -> VoiceSpeechOutcome | None:
    meta = message.meta if message.meta and hasattr(message.meta, "get") else None
    explicit = meta.get("speech_turn_outcome") if meta else None
    if explicit is not None:
        return VoiceSpeechOutcome(str(explicit))
    status = (
        message.request_status.value
        if hasattr(message.request_status, "value")
        else str(message.request_status)
        if message.request_status is not None
        else None
    )
    return {
        RequestStatus.COMPLETED.value: VoiceSpeechOutcome.DRAINED,
        RequestStatus.INTERRUPTED.value: VoiceSpeechOutcome.INTERRUPTED,
        RequestStatus.FAILED.value: VoiceSpeechOutcome.FAILED,
        RequestStatus.SKIPPED.value: VoiceSpeechOutcome.CANCELLED,
    }.get(status)


def _duration_ms(start: datetime | None, end: datetime | None) -> int | None:
    if not start or not end:
        return None
    return max(int((end - start).total_seconds() * 1000), 0)


def _extract_tool_fields(
    message: MessageInDb,
) -> tuple[str | None, str | None, dict[str, Any] | None, dict[str, Any] | None]:
    content = message.content
    if hasattr(content, "content"):
        inner = content.content
    elif isinstance(content, dict):
        inner = content.get("content")
    else:
        inner = None

    if message.kind == MessageKind.TOOL_USE:
        item = inner if not isinstance(inner, list) else inner[0]
        return (
            _tool_attr(item, "name"),
            _tool_attr(item, "id"),
            _tool_attr(item, "input"),
            None,
        )
    if message.kind == MessageKind.TOOL_RESULT:
        item = inner[0] if isinstance(inner, list) and inner else inner
        return (
            _tool_attr(item, "name"),
            _tool_attr(item, "tool_use_id"),
            None,
            {
                "content": _tool_attr(item, "content"),
                "is_error": _tool_attr(item, "is_error"),
            },
        )
    return None, None, None, None


def _tool_attr(item: Any, name: str) -> Any:
    if item is None:
        return None
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def now_utc() -> datetime:
    """Return the current UTC datetime for event integration points."""
    return arrow.utcnow().datetime
