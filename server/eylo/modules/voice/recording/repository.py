"""Repository layer for voice recording model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select

from eylo.common.database import get_transaction
from eylo.modules.voice.recording.model import VoiceRecordingModel


class VoiceRecordingRepository:
    """Data access for VoiceRecordingModel."""

    async def create(self, recording: VoiceRecordingModel) -> VoiceRecordingModel:
        session = get_transaction()
        session.add(recording)
        await session.flush()
        return recording

    async def get_by_conversation(
        self, *, organization_id: UUID, conversation_id: UUID
    ) -> list[VoiceRecordingModel]:
        session = get_transaction()
        result = await session.execute(
            select(VoiceRecordingModel)
            .where(VoiceRecordingModel.organization_id == organization_id)
            .where(VoiceRecordingModel.conversation_id == conversation_id)
            .where(VoiceRecordingModel.deleted.is_(False))
            .order_by(VoiceRecordingModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_session(
        self,
        *,
        organization_id: UUID,
        session_id: str,
    ) -> Optional[VoiceRecordingModel]:
        session = get_transaction()
        result = await session.execute(
            select(VoiceRecordingModel)
            .where(VoiceRecordingModel.organization_id == organization_id)
            .where(VoiceRecordingModel.session_id == session_id)
            .where(VoiceRecordingModel.deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        *,
        organization_id: UUID,
        recording_id: UUID,
    ) -> VoiceRecordingModel | None:
        session = get_transaction()
        result = await session.execute(
            select(VoiceRecordingModel).where(
                VoiceRecordingModel.id == recording_id,
                VoiceRecordingModel.organization_id == organization_id,
                VoiceRecordingModel.deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()
