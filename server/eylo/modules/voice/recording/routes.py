"""API routes for voice recordings."""

import logging
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from eylo.common.contracts.storage import StorageLocator
from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.services.conversations import ConversationService
from eylo.modules.voice.recording.service import (
    VoiceRecordingService,
    locator_from_recording,
)
from eylo.pipelines.voice.recording_storage import (
    RecordingObjectNotFound,
    RecordingStorageUnavailable,
    open_recording_stream,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organizations/{organization_id}/conversations/{conversation_id}/recordings",
    tags=["Voice Recordings"],
)


class VoiceRecordingResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    session_id: str
    voice_session_id: UUID
    telephony_call_id: UUID | None = None
    user_audio_url: Optional[str] = None
    agent_audio_url: Optional[str] = None
    user_duration_seconds: Optional[float] = None
    agent_duration_seconds: Optional[float] = None
    user_sample_rate: Optional[int] = None
    agent_sample_rate: Optional[int] = None
    upload_state: str
    upload_error: Optional[str] = None
    created_at: str


class RecordingListResponse(BaseModel):
    recordings: list[VoiceRecordingResponse]


class AudioStreamingResponse(StreamingResponse):
    """Document and return proxied WAV audio consistently."""

    media_type = "audio/wav"


@router.get("", response_model=RecordingListResponse)
async def list_recordings(
    organization_id: UUID,
    conversation_id: UUID,
    request: Request,
    current_user: CurrentUserSchema = Depends(get_current_user),
):
    """List all voice recordings for a conversation.

    Returns recording metadata with authenticated application download URLs.
    """
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)

    async with start_transaction(ro=True) as db:
        try:
            await ConversationService(db).get_by_organization_and_id(
                organization_id=current_user.organization_id,
                pk=conversation_id,
            )
        except ConversationNotFound:
            raise HTTPException(status_code=404) from None
        service = VoiceRecordingService()
        recordings = await service.get_by_conversation(
            organization_id=current_user.organization_id,
            conversation_id=conversation_id,
        )

    results = []
    for rec in recordings:
        results.append(
            VoiceRecordingResponse(
                id=rec.id,
                conversation_id=rec.conversation_id,
                session_id=rec.session_id,
                voice_session_id=rec.voice_session_id,
                telephony_call_id=rec.telephony_call_id,
                user_audio_url=_recording_download_url(
                    request=request,
                    locator=locator_from_recording(rec, track="user"),
                    recording_id=rec.id,
                    track_name="user",
                    organization_id=current_user.organization_id,
                    conversation_id=conversation_id,
                ),
                agent_audio_url=_recording_download_url(
                    request=request,
                    locator=locator_from_recording(rec, track="agent"),
                    recording_id=rec.id,
                    track_name="agent",
                    organization_id=current_user.organization_id,
                    conversation_id=conversation_id,
                ),
                user_duration_seconds=rec.user_duration_seconds,
                agent_duration_seconds=rec.agent_duration_seconds,
                user_sample_rate=rec.user_sample_rate,
                agent_sample_rate=rec.agent_sample_rate,
                upload_state=rec.state.value,
                upload_error=(rec.meta or {}).get("upload_error"),
                created_at=rec.created_at.isoformat() if rec.created_at else "",
            )
        )

    return RecordingListResponse(recordings=results)


def _recording_download_url(
    *,
    request: Request,
    locator: StorageLocator | None,
    recording_id: UUID,
    track_name: str,
    organization_id: UUID,
    conversation_id: UUID,
) -> str | None:
    if locator is None:
        return None
    return str(
        request.url_for(
            "download_recording_track",
            organization_id=str(organization_id),
            conversation_id=str(conversation_id),
            recording_id=str(recording_id),
            track=track_name,
        )
    )


@router.get(
    "/{recording_id}/{track}",
    name="download_recording_track",
    response_class=AudioStreamingResponse,
)
async def download_recording_track(
    organization_id: UUID,
    conversation_id: UUID,
    recording_id: UUID,
    track: Literal["user", "agent"],
    current_user: CurrentUserSchema = Depends(get_current_user),
) -> AudioStreamingResponse:
    """Stream one organization-owned recording track through bearer auth."""
    if organization_id != current_user.organization_id:
        raise HTTPException(status_code=404)

    async with start_transaction(ro=True) as db:
        try:
            await ConversationService(db).get_by_organization_and_id(
                organization_id=current_user.organization_id,
                pk=conversation_id,
            )
        except ConversationNotFound:
            raise HTTPException(status_code=404) from None
        recording = await VoiceRecordingService().get_by_id(
            organization_id=current_user.organization_id,
            recording_id=recording_id,
        )
        if recording is None or recording.conversation_id != conversation_id:
            raise HTTPException(status_code=404)
        locator = locator_from_recording(recording, track=track)
        if locator is None:
            raise HTTPException(status_code=404)

    try:
        opened = await open_recording_stream(locator)
    except RecordingObjectNotFound:
        raise HTTPException(status_code=404) from None
    except RecordingStorageUnavailable:
        logger.warning(
            "Unable to stream %s track on recording %s for organization %s",
            track,
            recording_id,
            organization_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Recording storage is temporarily unavailable.",
        ) from None

    return AudioStreamingResponse(
        opened.content,
        media_type=opened.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Length": str(opened.size),
            "Content-Disposition": (
                f'inline; filename="recording-{recording_id}-{track}.wav"'
            ),
        },
    )
