"""Domain service for reusable organization-owned Voice Configs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.config import settings
from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.common.database import get_transaction
from eylo.modules.storage_configs.wiring import (
    build_storage_config_resolver,
    build_storage_config_service,
)
from eylo.modules.voice.exceptions import (
    RealtimeVoiceDisabledError,
    VoiceConfigConflict,
    VoiceConfigNotFound,
)
from eylo.modules.voice.models import VoiceConfigModel
from eylo.modules.voice.repositories.voice_configs import VoiceConfigRepository
from eylo.modules.voice.schemas.api import (
    OrganizationVoiceConfigCreate,
    OrganizationVoiceConfigUpdate,
    VoiceConfig,
    VoiceConfigRead,
    validate_voice_config_section,
)
from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.wiring import build_voice_config_resolver
from eylo.modules.voice_configs.wiring import (
    build_voice_config_service as build_provider_voice_config_service,
)

PROVIDER_KINDS = ("stt", "tts", "realtime", "storage")
PROVIDER_ID_FIELDS = tuple(f"{kind}_provider_config_id" for kind in PROVIDER_KINDS)
PROVIDER_REVISION_FIELDS = tuple(
    f"{kind}_provider_config_revision" for kind in PROVIDER_KINDS
)
NON_DEFINITION_FIELDS = {
    *PROVIDER_ID_FIELDS,
    *PROVIDER_REVISION_FIELDS,
    "capabilities",
}


@dataclass(frozen=True, slots=True)
class VoiceConfigPublication:
    """Exact Voice Config authority copied into one Agent revision."""

    voice_config_id: UUID
    voice_config_revision: int
    config: VoiceConfig


class VoiceConfigService:
    """Own current Voice Config definitions; publication owns history."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()
        self.repository = VoiceConfigRepository(self._db)

    async def list(self, organization_id: UUID) -> list[VoiceConfigRead]:
        rows = await self._db.scalars(
            select(VoiceConfigModel)
            .where(
                VoiceConfigModel.organization_id == organization_id,
                VoiceConfigModel.deleted.is_(False),
            )
            .order_by(func.lower(VoiceConfigModel.name), VoiceConfigModel.id)
        )
        return [self._read(row) for row in rows.all()]

    async def get(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        for_update: bool = False,
    ) -> VoiceConfigRead:
        return self._read(
            await self._get_model(
                organization_id=organization_id,
                voice_config_id=voice_config_id,
                for_update=for_update,
            )
        )

    async def create(
        self,
        *,
        organization_id: UUID,
        payload: OrganizationVoiceConfigCreate,
    ) -> VoiceConfigRead:
        await self._require_unique_name(
            organization_id=organization_id,
            name=payload.name,
        )
        config = self._validated_config(payload.config)
        await self._validate_provider_references(config, organization_id)

        row = VoiceConfigModel(
            organization_id=organization_id,
            name=payload.name,
            description=payload.description,
            revision=1,
        )
        self._assign_config(row, config)
        await self.repository.save_(row)
        return self._read(row)

    async def update(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        payload: OrganizationVoiceConfigUpdate,
    ) -> VoiceConfigRead:
        row = await self._get_model(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            for_update=True,
        )
        if row.revision != payload.expected_revision:
            raise VoiceConfigConflict(
                "Voice Config revision conflict: "
                f"expected {payload.expected_revision}, found {row.revision}."
            )

        if "name" in payload.model_fields_set:
            assert payload.name is not None
            await self._require_unique_name(
                organization_id=organization_id,
                name=payload.name,
                excluding_id=row.id,
            )
            row.name = payload.name
        if "description" in payload.model_fields_set:
            row.description = payload.description
        if "config" in payload.model_fields_set:
            assert payload.config is not None
            config = self._validated_config(payload.config)
            await self._validate_provider_references(config, organization_id)
            self._assign_config(row, config)

        row.revision += 1
        await self.repository.save_(row)
        return self._read(row)

    async def patch_section(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        section: str,
        data: Any,
        expected_revision: int,
    ) -> VoiceConfigRead:
        try:
            section_value = validate_voice_config_section(section, data)
        except (TypeError, ValueError, ValidationError) as error:
            raise ValueError(str(error)) from error

        current = await self.get(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )
        config = current.config.model_copy(deep=True)
        setattr(config, section, section_value)
        return await self.update(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            payload=OrganizationVoiceConfigUpdate(
                expected_revision=expected_revision,
                config=config,
            ),
        )

    async def delete(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> None:
        row = await self._get_model(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
            for_update=True,
        )
        await self.repository.delete_(row)

    async def resolve_for_publish(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        expected_revision: int,
    ) -> VoiceConfigPublication:
        """Resolve provider revisions without changing the editable definition."""
        row = await self._get_model(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )
        if row.revision != expected_revision:
            raise VoiceConfigConflict(
                "The Agent's Voice Config binding is stale. Reload the Agent "
                "before publishing."
            )

        config = self._config_from_model(row)
        resolver = build_voice_config_resolver(self._db)
        if config.realtime_provider_config_id is not None:
            config.stt_provider_config_revision = None
            config.tts_provider_config_revision = None
            resolved = await resolver.resolve_realtime(
                organization_id,
                provider_config_id=config.realtime_provider_config_id,
            )
            config.realtime_provider_config_revision = (
                resolved.provider_config_revision
            )
        else:
            if config.stt_provider_config_id is None:
                raise ValueError(
                    "Assign a ready STT config before publishing a voice agent."
                )
            if config.tts_provider_config_id is None:
                raise ValueError(
                    "Assign a ready TTS config before publishing a voice agent."
                )
            resolved_stt = await resolver.resolve_stt(
                organization_id,
                provider_config_id=config.stt_provider_config_id,
            )
            resolved_tts = await resolver.resolve_tts(
                organization_id,
                provider_config_id=config.tts_provider_config_id,
            )
            config.stt_provider_config_revision = (
                resolved_stt.provider_config_revision
            )
            config.tts_provider_config_revision = (
                resolved_tts.provider_config_revision
            )
            config.realtime_provider_config_revision = None

        if config.artifacts.audio_storage_enabled:
            if config.storage_provider_config_id is None:
                raise ValueError(
                    "Assign a ready storage config before publishing a voice "
                    "agent with audio storage enabled."
                )
        if config.storage_provider_config_id is not None:
            resolved_storage = await build_storage_config_resolver(self._db).resolve(
                organization_id,
                provider_config_id=config.storage_provider_config_id,
            )
            config.storage_provider_config_revision = (
                resolved_storage.provider_config_revision
            )
        else:
            config.storage_provider_config_revision = None

        return VoiceConfigPublication(
            voice_config_id=row.id,
            voice_config_revision=row.revision,
            config=config,
        )

    async def _get_model(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
        for_update: bool = False,
    ) -> VoiceConfigModel:
        query = select(VoiceConfigModel).where(
            VoiceConfigModel.id == voice_config_id,
            VoiceConfigModel.organization_id == organization_id,
            VoiceConfigModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self._db.scalar(query)
        if row is None:
            raise VoiceConfigNotFound("Voice Config not found.")
        return row

    async def _require_unique_name(
        self,
        *,
        organization_id: UUID,
        name: str,
        excluding_id: UUID | None = None,
    ) -> None:
        query = select(VoiceConfigModel.id).where(
            VoiceConfigModel.organization_id == organization_id,
            VoiceConfigModel.name == name,
            VoiceConfigModel.deleted.is_(False),
        )
        if excluding_id is not None:
            query = query.where(VoiceConfigModel.id != excluding_id)
        if await self._db.scalar(query) is not None:
            raise VoiceConfigConflict(
                "A Voice Config with this name already exists in the organization."
            )

    def _validated_config(self, source: VoiceConfig) -> VoiceConfig:
        for field_name in PROVIDER_REVISION_FIELDS:
            if getattr(source, field_name) is not None:
                raise ValueError(
                    "Provider revisions are resolved only when an Agent is published."
                )
        if source.capabilities is not None:
            raise ValueError(
                "Voice capabilities are reported by the platform and cannot be set."
            )
        config = source.model_copy(deep=True)
        self._assert_realtime_voice_enabled(config)
        return config

    def _read(self, row: VoiceConfigModel) -> VoiceConfigRead:
        return VoiceConfigRead(
            id=row.id,
            organization_id=row.organization_id,
            name=row.name,
            description=row.description,
            revision=row.revision,
            config=self._config_from_model(row),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _config_from_model(self, row: VoiceConfigModel) -> VoiceConfig:
        return VoiceConfig.model_validate(
            {
                **dict(row.definition or {}),
                **{
                    field_name: getattr(row, field_name)
                    for field_name in PROVIDER_ID_FIELDS
                },
            }
        )

    @staticmethod
    def _assign_config(row: VoiceConfigModel, config: VoiceConfig) -> None:
        for field_name in PROVIDER_ID_FIELDS:
            setattr(row, field_name, getattr(config, field_name))
        row.definition = config.model_dump(
            mode="json",
            exclude=NON_DEFINITION_FIELDS,
        )

    async def _validate_provider_references(
        self,
        config: VoiceConfig,
        organization_id: UUID,
    ) -> None:
        try:
            provider_configs = build_provider_voice_config_service(self._db)
            if config.stt_provider_config_id is not None:
                await provider_configs.get(
                    organization_id=organization_id,
                    config_id=config.stt_provider_config_id,
                    kind=VoiceKind.STT,
                )
            if config.tts_provider_config_id is not None:
                await provider_configs.get(
                    organization_id=organization_id,
                    config_id=config.tts_provider_config_id,
                    kind=VoiceKind.TTS,
                )
            if config.realtime_provider_config_id is not None:
                await provider_configs.get(
                    organization_id=organization_id,
                    config_id=config.realtime_provider_config_id,
                    kind=VoiceKind.REALTIME,
                )
            if config.storage_provider_config_id is not None:
                await build_storage_config_service(self._db).get(
                    organization_id=organization_id,
                    config_id=config.storage_provider_config_id,
                )
        except ProviderConfigError as error:
            raise VoiceConfigNotFound(
                "Voice provider config was not found in this organization."
            ) from error

    @staticmethod
    def _assert_realtime_voice_enabled(config: VoiceConfig) -> None:
        if (
            config.realtime_provider_config_id is not None
            and not settings.ENABLE_REALTIME_VOICE
        ):
            raise RealtimeVoiceDisabledError("Realtime voice is disabled.")


__all__ = ["VoiceConfigPublication", "VoiceConfigService"]
