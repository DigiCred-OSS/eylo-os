"""Private admin routes for voice transcript sessions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from eylo.common.database import start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.voice_transcripts.constants import (
    VoiceRuntimeMode,
    VoiceSessionStatus,
)
from eylo.modules.voice_transcripts.controllers import VoiceTranscriptController
from eylo.modules.voice_transcripts.schemas.api import (
    VoiceSessionDetail,
    VoiceSessionListResponse,
)

router = APIRouter(
    prefix="/{organization_id}/voice-sessions", tags=["Voice Transcripts"]
)
conversation_router = APIRouter(
    prefix="/{organization_id}/conversations", tags=["Voice Transcripts"]
)


@router.get("", response_model=VoiceSessionListResponse)
async def list_voice_sessions(
    organization_id: UUID,
    current_user: CurrentUserSchema = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    conversation_id: UUID | None = None,
    agent_id: UUID | None = None,
    status: VoiceSessionStatus | None = None,
    runtime_mode: VoiceRuntimeMode | None = None,
) -> VoiceSessionListResponse:
    """List voice transcript sessions visible to the current organization."""
    async with start_transaction(ro=True) as db:
        return await VoiceTranscriptController(db).list_sessions(
            organization_id=organization_id,
            current_user=current_user,
            page=page,
            limit=limit,
            conversation_id=conversation_id,
            agent_id=agent_id,
            status=status,
            runtime_mode=runtime_mode,
        )


@router.get("/{voice_session_id}", response_model=VoiceSessionDetail)
async def get_voice_session(
    organization_id: UUID,
    voice_session_id: UUID,
    request: Request,
    current_user: CurrentUserSchema = Depends(get_current_user),
    segment_page: Annotated[int, Query(ge=1)] = 1,
    segment_limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> VoiceSessionDetail:
    """Get one voice transcript session with ordered timeline segments."""
    async with start_transaction(ro=True) as db:
        return await VoiceTranscriptController(db).get_session_detail(
            organization_id=organization_id,
            voice_session_id=voice_session_id,
            current_user=current_user,
            request=request,
            segment_page=segment_page,
            segment_limit=segment_limit,
        )


@conversation_router.get(
    "/{conversation_id}/voice-session", response_model=VoiceSessionDetail
)
async def get_voice_session_for_conversation(
    organization_id: UUID,
    conversation_id: UUID,
    request: Request,
    current_user: CurrentUserSchema = Depends(get_current_user),
    segment_page: Annotated[int, Query(ge=1)] = 1,
    segment_limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> VoiceSessionDetail:
    """Get the voice transcript session attached to a conversation."""
    async with start_transaction(ro=True) as db:
        return await VoiceTranscriptController(db).get_session_by_conversation(
            organization_id=organization_id,
            conversation_id=conversation_id,
            current_user=current_user,
            request=request,
            segment_page=segment_page,
            segment_limit=segment_limit,
        )
