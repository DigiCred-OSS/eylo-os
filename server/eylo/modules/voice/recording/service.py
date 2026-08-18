"""Service layer for voice recording persistence."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from eylo.absurd_work import DEFAULT_MAX_ATTEMPTS, DurableState
from eylo.common.contracts.storage import StorageAuthority, StorageLocator
from eylo.modules.voice.recording.model import VoiceRecordingModel
from eylo.modules.voice.recording.repository import VoiceRecordingRepository

logger = logging.getLogger(__name__)


class VoiceRecordingService:
    """CRUD operations for voice recording metadata."""

    def __init__(self) -> None:
        self._repo = VoiceRecordingRepository()

    async def file_upload(
        self,
        *,
        recording_id: UUID,
        organization_id: UUID,
        conversation_id: UUID,
        session_id: str,
        voice_session_id: UUID,
        telephony_call_id: UUID | None,
        storage_provider_config_id: UUID,
        storage_provider_config_revision: int,
        user_wav: bytes | None,
        agent_wav: bytes | None,
        user_storage_key: str | None,
        agent_storage_key: str | None,
        user_duration_seconds: float,
        agent_duration_seconds: float,
        user_sample_rate: int,
        agent_sample_rate: int,
    ) -> VoiceRecordingModel:
        """Commit captured audio before any provider upload is attempted."""
        if user_wav is None and agent_wav is None:
            raise ValueError("A recording upload requires at least one audio track.")
        recording = VoiceRecordingModel(
            id=recording_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            session_id=session_id,
            voice_session_id=voice_session_id,
            telephony_call_id=telephony_call_id,
            storage_provider_config_id=storage_provider_config_id,
            storage_provider_config_revision=storage_provider_config_revision,
            target_user_storage_key=user_storage_key,
            target_agent_storage_key=agent_storage_key,
            staged_user_wav=user_wav,
            staged_agent_wav=agent_wav,
            user_duration_seconds=user_duration_seconds,
            agent_duration_seconds=agent_duration_seconds,
            user_sample_rate=user_sample_rate,
            agent_sample_rate=agent_sample_rate,
            state=DurableState.PENDING,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            meta={"upload_state": DurableState.PENDING.value},
        )
        return await self._repo.create(recording)

    async def record_unavailable_upload(
        self,
        *,
        recording_id: UUID,
        organization_id: UUID,
        conversation_id: UUID,
        session_id: str,
        voice_session_id: UUID,
        telephony_call_id: UUID | None,
        reason: str,
        user_duration_seconds: float,
        agent_duration_seconds: float,
        user_sample_rate: int,
        agent_sample_rate: int,
    ) -> VoiceRecordingModel:
        """Persist a terminal failure without letting it escape call teardown."""
        now = datetime.now(timezone.utc)
        recording = VoiceRecordingModel(
            id=recording_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            session_id=session_id,
            voice_session_id=voice_session_id,
            telephony_call_id=telephony_call_id,
            user_duration_seconds=user_duration_seconds,
            agent_duration_seconds=agent_duration_seconds,
            user_sample_rate=user_sample_rate,
            agent_sample_rate=agent_sample_rate,
            state=DurableState.FAILED,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            finished_at=now,
            last_error=reason[:2000],
            meta={
                "upload_state": DurableState.FAILED.value,
                "upload_error": reason[:2000],
            },
        )
        return await self._repo.create(recording)

    async def create_recording(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        session_id: str,
        voice_session_id: UUID,
        telephony_call_id: UUID | None = None,
        recording_id: UUID | None = None,
        user_locator: StorageLocator | None = None,
        agent_locator: StorageLocator | None = None,
        user_duration_seconds: Optional[float] = None,
        agent_duration_seconds: Optional[float] = None,
        user_sample_rate: Optional[int] = None,
        agent_sample_rate: Optional[int] = None,
        meta: Optional[dict] = None,
    ) -> VoiceRecordingModel:
        """Create a new voice recording entry."""
        authority = _shared_authority(user_locator, agent_locator)
        recording = VoiceRecordingModel(
            organization_id=organization_id,
            conversation_id=conversation_id,
            session_id=session_id,
            voice_session_id=voice_session_id,
            telephony_call_id=telephony_call_id,
            # Provider and filesystem locations are server-side authority only.
            # Members download through the authenticated recording route.
            user_audio_url=None,
            agent_audio_url=None,
            storage_provider_config_id=(
                authority.provider_config_id if authority else None
            ),
            storage_provider_config_revision=(
                authority.provider_config_revision if authority else None
            ),
            storage_provider=authority.provider if authority else None,
            storage_authority=dict(authority.location) if authority else None,
            user_storage_key=user_locator.key if user_locator else None,
            agent_storage_key=agent_locator.key if agent_locator else None,
            user_duration_seconds=user_duration_seconds,
            agent_duration_seconds=agent_duration_seconds,
            user_sample_rate=user_sample_rate,
            agent_sample_rate=agent_sample_rate,
            state=DurableState.SUCCEEDED,
            attempts=1,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            meta={
                **(meta or {}),
                "upload_state": DurableState.SUCCEEDED.value,
            },
        )
        if recording_id is not None:
            recording.id = recording_id
        return await self._repo.create(recording)

    async def get_by_conversation(
        self, *, organization_id: UUID, conversation_id: UUID
    ) -> list[VoiceRecordingModel]:
        """Get all recordings for a conversation."""
        return await self._repo.get_by_conversation(
            organization_id=organization_id,
            conversation_id=conversation_id,
        )

    async def get_by_session(
        self,
        *,
        organization_id: UUID,
        session_id: str,
    ) -> Optional[VoiceRecordingModel]:
        """Get recording for a specific session."""
        return await self._repo.get_by_session(
            organization_id=organization_id,
            session_id=session_id,
        )

    async def get_by_id(
        self,
        *,
        organization_id: UUID,
        recording_id: UUID,
    ) -> VoiceRecordingModel | None:
        return await self._repo.get_by_id(
            organization_id=organization_id,
            recording_id=recording_id,
        )


def _shared_authority(
    user_locator: StorageLocator | None,
    agent_locator: StorageLocator | None,
) -> StorageAuthority | None:
    locators = [locator for locator in (user_locator, agent_locator) if locator]
    if not locators:
        return None
    authority = locators[0].authority
    if any(locator.authority != authority for locator in locators[1:]):
        raise ValueError("Recording tracks must use one storage authority.")
    return authority


def locator_from_recording(
    recording: VoiceRecordingModel,
    *,
    track: str,
) -> StorageLocator | None:
    key = {
        "user": recording.user_storage_key,
        "agent": recording.agent_storage_key,
    }.get(track)
    if key is None:
        return None
    if (
        recording.storage_provider_config_id is None
        or recording.storage_provider_config_revision is None
        or recording.storage_provider is None
        or recording.storage_authority is None
    ):
        raise ValueError(f"Recording {recording.id} has an incomplete locator.")
    authority = StorageAuthority(
        organization_id=recording.organization_id,
        provider_config_id=recording.storage_provider_config_id,
        provider_config_revision=recording.storage_provider_config_revision,
        provider=recording.storage_provider,
        location=recording.storage_authority,
    )
    return authority.locate(key)
