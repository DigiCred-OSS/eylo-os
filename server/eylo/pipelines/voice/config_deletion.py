"""Block STT/TTS config deletion while an agent voice definition references it."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import start_transaction
from eylo.modules.agents.models import AgentRevisionModel
from eylo.modules.voice.models import VoiceConfigModel
from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.wiring import build_voice_config_service


class VoiceConfigReferenceLookup:
    def __init__(self, db: AsyncSession, kind: VoiceKind) -> None:
        self._db = db
        columns_by_kind = {
            VoiceKind.STT: (
                VoiceConfigModel.stt_provider_config_id,
                AgentRevisionModel.stt_provider_config_id,
            ),
            VoiceKind.TTS: (
                VoiceConfigModel.tts_provider_config_id,
                AgentRevisionModel.tts_provider_config_id,
            ),
            VoiceKind.REALTIME: (
                VoiceConfigModel.realtime_provider_config_id,
                AgentRevisionModel.realtime_provider_config_id,
            ),
        }
        columns = columns_by_kind[kind]
        self._references = (
            (VoiceConfigModel, columns[0]),
            (AgentRevisionModel, columns[1]),
        )

    async def has_references(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> bool:
        for model, column in self._references:
            referenced = await self._db.scalar(
                select(
                    exists().where(
                        model.organization_id == organization_id,
                        column == config_id,
                        model.deleted.is_(False),
                    )
                )
            )
            if referenced:
                return True
        return False


class VoiceConfigDeletionUseCase:
    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        kind: VoiceKind,
    ) -> None:
        async with start_transaction() as db:
            references = VoiceConfigReferenceLookup(db, kind)
            await build_voice_config_service(
                db,
                references=references,
            ).delete(
                organization_id=organization_id,
                config_id=config_id,
                kind=kind,
            )
