"""HTTP controllers for private voice transcript routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.contracts.storage import StorageLocator
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.voice.recording.service import (
    VoiceRecordingService,
    locator_from_recording,
)
from eylo.modules.voice_transcripts.constants import (
    VoiceRuntimeMode,
    VoiceSessionStatus,
)
from eylo.modules.voice_transcripts.schemas.api import (
    VoiceSegmentResponse,
    VoiceSessionDetail,
    VoiceSessionListResponse,
    VoiceSessionSummary,
    VoiceTranscriptAudioUrls,
)
from eylo.modules.voice_transcripts.services.indb import VoiceTranscriptService


class VoiceTranscriptController:
    """Request-facing orchestration for voice transcript APIs."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self.service = VoiceTranscriptService(db)

    async def list_sessions(
        self,
        *,
        organization_id: UUID,
        current_user: CurrentUserSchema,
        page: int,
        limit: int,
        conversation_id: UUID | None = None,
        agent_id: UUID | None = None,
        status: VoiceSessionStatus | None = None,
        runtime_mode: VoiceRuntimeMode | None = None,
    ) -> VoiceSessionListResponse:
        """Return organization-scoped voice sessions for the admin list view."""
        _ensure_org_access(organization_id, current_user)
        offset = (page - 1) * limit
        sessions = await self.service.list_sessions(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            conversation_id=conversation_id,
            agent_id=agent_id,
            status=status,
            runtime_mode=runtime_mode,
        )
        total = await self.service.count_sessions(
            organization_id=organization_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            status=status,
            runtime_mode=runtime_mode,
        )
        return VoiceSessionListResponse(
            data=[VoiceSessionSummary.model_validate(item) for item in sessions],
            total=total,
            page=page,
            limit=limit,
            has_more=offset + len(sessions) < total,
        )

    async def get_session_detail(
        self,
        *,
        organization_id: UUID,
        voice_session_id: UUID,
        current_user: CurrentUserSchema,
        request: Request,
        segment_page: int,
        segment_limit: int,
    ) -> VoiceSessionDetail:
        """Return a voice session with ordered segments and short-lived audio URLs."""
        _ensure_org_access(organization_id, current_user)
        session = await self.service.get_session(
            organization_id=organization_id, session_id=voice_session_id
        )
        if not session:
            raise HTTPException(status_code=404, detail="Voice session not found")
        segment_offset = (segment_page - 1) * segment_limit
        segments = await self.service.list_segments(
            session.id,
            limit=segment_limit,
            offset=segment_offset,
        )
        segment_total = await self.service.count_segments(session.id)
        audio_urls = await _build_audio_urls(
            request=request,
            conversation_id=session.conversation_id,
            user_recording_id=session.user_audio_recording_id,
            assistant_recording_id=session.assistant_audio_recording_id,
            user_locator=await _recording_locator(
                organization_id,
                session.user_audio_recording_id,
                track="user",
            ),
            assistant_locator=await _recording_locator(
                organization_id,
                session.assistant_audio_recording_id,
                track="agent",
            ),
            organization_id=organization_id,
        )
        return VoiceSessionDetail(
            **VoiceSessionSummary.model_validate(session).model_dump(),
            user_audio_url=None,
            assistant_audio_url=None,
            combined_audio_url=None,
            audio_urls=audio_urls,
            segments=[VoiceSegmentResponse.model_validate(item) for item in segments],
            segment_total=segment_total,
            segment_page=segment_page,
            segment_limit=segment_limit,
            segments_has_more=segment_offset + len(segments) < segment_total,
            metrics=session.metrics,
            meta=session.meta,
        )

    async def get_session_by_conversation(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        current_user: CurrentUserSchema,
        request: Request,
        segment_page: int,
        segment_limit: int,
    ) -> VoiceSessionDetail:
        """Return voice transcript detail for a conversation, if one exists."""
        _ensure_org_access(organization_id, current_user)
        session = await self.service.get_by_conversation(
            organization_id=organization_id,
            conversation_id=conversation_id,
        )
        if not session:
            raise HTTPException(status_code=404, detail="Voice session not found")
        return await self.get_session_detail(
            organization_id=organization_id,
            voice_session_id=session.id,
            current_user=current_user,
            request=request,
            segment_page=segment_page,
            segment_limit=segment_limit,
        )


async def _build_audio_urls(
    *,
    request: Request,
    conversation_id: UUID,
    user_recording_id: UUID | None,
    assistant_recording_id: UUID | None,
    user_locator: StorageLocator | None,
    assistant_locator: StorageLocator | None,
    organization_id: UUID,
) -> VoiceTranscriptAudioUrls:
    return VoiceTranscriptAudioUrls(
        user=_recording_audio_url(
            request=request,
            organization_id=organization_id,
            conversation_id=conversation_id,
            recording_id=user_recording_id,
            track="user",
            locator=user_locator,
        ),
        assistant=_recording_audio_url(
            request=request,
            organization_id=organization_id,
            conversation_id=conversation_id,
            recording_id=assistant_recording_id,
            track="agent",
            locator=assistant_locator,
        ),
        combined=None,
    )


def _recording_audio_url(
    *,
    request: Request,
    organization_id: UUID,
    conversation_id: UUID,
    recording_id: UUID | None,
    track: str,
    locator: StorageLocator | None,
) -> str | None:
    if locator is None or recording_id is None:
        return None
    return str(
        request.url_for(
            "download_recording_track",
            organization_id=str(organization_id),
            conversation_id=str(conversation_id),
            recording_id=str(recording_id),
            track=track,
        )
    )


async def _recording_locator(
    organization_id: UUID,
    recording_id: UUID | None,
    *,
    track: str,
) -> StorageLocator | None:
    if recording_id is None:
        return None
    recording = await VoiceRecordingService().get_by_id(
        organization_id=organization_id,
        recording_id=recording_id,
    )
    if recording is None:
        return None
    return locator_from_recording(recording, track=track)


def _ensure_org_access(organization_id: UUID, current_user: CurrentUserSchema) -> None:
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)
