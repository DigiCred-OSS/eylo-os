"""Resolve effective organization voice configs (STT/TTS)."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.voice_configs.catalog import VoiceKind
from eylo.modules.voice_configs.domain import (
    InvalidVoiceConfig,
    ResolvedRealtime,
    ResolvedSTT,
    ResolvedTTS,
)
from eylo.modules.voice_configs.service import VoiceConfigService

__all__ = ["VoiceConfigResolver"]


class VoiceConfigResolver:
    """Resolves org-scoped STT/TTS provider configs."""

    def __init__(self, configs: VoiceConfigService) -> None:
        self._configs = configs

    async def resolve_stt(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedSTT:
        if provider_config_id is None:
            raise _not_configured(VoiceKind.STT, "provider_config")
        provider_config = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            kind=VoiceKind.STT,
            granted=True,
        )
        return _to_resolved_stt(provider_config, organization_id)

    async def resolve_stt_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedSTT:
        provider_config = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            kind=VoiceKind.STT,
            granted=True,
        )
        return _to_resolved_stt(provider_config, organization_id)

    async def resolve_tts(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedTTS:
        if provider_config_id is None:
            raise _not_configured(VoiceKind.TTS, "provider_config")
        provider_config = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            kind=VoiceKind.TTS,
            granted=True,
        )
        return _to_resolved_tts(provider_config, organization_id)

    async def resolve_tts_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedTTS:
        provider_config = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            kind=VoiceKind.TTS,
            granted=True,
        )
        return _to_resolved_tts(provider_config, organization_id)

    async def resolve_realtime(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedRealtime:
        if provider_config_id is None:
            raise _not_configured(VoiceKind.REALTIME, "provider_config")
        provider_config = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            kind=VoiceKind.REALTIME,
            granted=True,
        )
        return _to_resolved_realtime(provider_config, organization_id)

    async def resolve_realtime_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedRealtime:
        provider_config = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            kind=VoiceKind.REALTIME,
            granted=True,
        )
        return _to_resolved_realtime(provider_config, organization_id)


def _to_resolved_stt(provider_config, organization_id: UUID) -> ResolvedSTT:
    try:
        return ResolvedSTT.from_provider_config(
            provider_config_id=provider_config.provider_config_id,
            organization_id=organization_id,
            provider_config=provider_config,
        )
    except InvalidVoiceConfig:
        raise _not_configured(VoiceKind.STT, "valid_provider_config") from None


def _to_resolved_tts(provider_config, organization_id: UUID) -> ResolvedTTS:
    try:
        return ResolvedTTS.from_provider_config(
            provider_config_id=provider_config.provider_config_id,
            organization_id=organization_id,
            provider_config=provider_config,
        )
    except InvalidVoiceConfig:
        raise _not_configured(VoiceKind.TTS, "valid_provider_config") from None


def _to_resolved_realtime(
    provider_config,
    organization_id: UUID,
) -> ResolvedRealtime:
    try:
        return ResolvedRealtime.from_provider_config(
            provider_config_id=provider_config.provider_config_id,
            organization_id=organization_id,
            provider_config=provider_config,
        )
    except InvalidVoiceConfig:
        raise _not_configured(
            VoiceKind.REALTIME,
            "valid_provider_config",
        ) from None


def _not_configured(kind: VoiceKind, missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability(kind.value),
        missing=[missing],
        configure_via=f"/api/{kind.value}-configs",
    )
