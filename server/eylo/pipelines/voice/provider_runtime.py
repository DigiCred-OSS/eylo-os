"""Resolve the exact STT/TTS revisions pinned to an agent voice definition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.voice.schemas.api import VoiceConfig
from eylo.modules.voice_configs.domain import (
    ResolvedRealtime,
    ResolvedSTT,
    ResolvedTTS,
)
from eylo.modules.voice_configs.wiring import build_voice_config_resolver


async def resolve_decomposed_voice_runtime(
    organization_id: UUID,
    voice_config: VoiceConfig,
    *,
    db: AsyncSession | None = None,
) -> tuple[ResolvedSTT, ResolvedTTS]:
    """Resolve pinned provider material; never substitute a current revision."""
    if (
        voice_config.stt_provider_config_id is None
        or voice_config.stt_provider_config_revision is None
    ):
        raise _not_configured(Capability.STT, "/api/stt-configs")
    if (
        voice_config.tts_provider_config_id is None
        or voice_config.tts_provider_config_revision is None
    ):
        raise _not_configured(Capability.TTS, "/api/tts-configs")

    resolver = build_voice_config_resolver(db)
    stt = await resolver.resolve_stt_pinned(
        organization_id,
        provider_config_id=voice_config.stt_provider_config_id,
        revision=voice_config.stt_provider_config_revision,
    )
    tts = await resolver.resolve_tts_pinned(
        organization_id,
        provider_config_id=voice_config.tts_provider_config_id,
        revision=voice_config.tts_provider_config_revision,
    )
    return stt, tts


async def resolve_realtime_voice_runtime(
    organization_id: UUID,
    voice_config: VoiceConfig,
    *,
    db: AsyncSession | None = None,
) -> ResolvedRealtime:
    """Resolve the exact realtime provider revision pinned at Agent publish."""
    if (
        voice_config.realtime_provider_config_id is None
        or voice_config.realtime_provider_config_revision is None
    ):
        raise _not_configured(Capability.REALTIME, "/api/realtime-configs")
    return await build_voice_config_resolver(db).resolve_realtime_pinned(
        organization_id,
        provider_config_id=voice_config.realtime_provider_config_id,
        revision=voice_config.realtime_provider_config_revision,
    )


@dataclass(frozen=True, slots=True)
class DecomposedVoiceRuntimeIdentity:
    """Provider identity actually used by one decomposed voice session."""

    stt_vendor: str
    stt_model: str | None
    tts_vendor: str
    tts_model: str | None
    tts_voice: str | None

    @classmethod
    def from_resolved(
        cls,
        stt: ResolvedSTT,
        tts: ResolvedTTS,
    ) -> DecomposedVoiceRuntimeIdentity:
        return cls(
            stt_vendor=stt.provider.value,
            stt_model=_optional_text(
                stt.config.get("model") or stt.config.get("language_model_name")
            ),
            tts_vendor=tts.provider.value,
            tts_model=_optional_text(tts.config.get("model")),
            tts_voice=_optional_text(tts.config.get("voice")),
        )


def build_stt_runtime_config(
    voice_config: VoiceConfig,
    stt: ResolvedSTT,
    *,
    transport: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Compose platform speech policy with one pinned STT provider revision."""
    config: dict[str, Any] = {}
    start_plan = voice_config.start_speaking_plan
    if start_plan is not None:
        config["wait_ms"] = start_plan.wait_ms
    stop_plan = voice_config.stop_speaking_plan
    if stop_plan is not None:
        config["interruption_type"] = stop_plan.interruption_type.value

    config.update(stt.config)
    config.update(stt.secrets)
    config.update(_transport_without_vendor(transport))
    config["vendor"] = stt.provider.value
    return config


def build_tts_runtime_config(
    tts: ResolvedTTS,
    *,
    transport: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Compose one pinned TTS provider revision with transport facts."""
    config: dict[str, Any] = {}
    config.update(tts.config)
    config.update(tts.secrets)
    config.update(_transport_without_vendor(transport))
    config["vendor"] = tts.provider.value
    return config


def _transport_without_vendor(
    transport: Mapping[str, object] | None,
) -> dict[str, object]:
    values = dict(transport or {})
    values.pop("vendor", None)
    return values


def _optional_text(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _not_configured(
    capability: Capability,
    configure_via: str,
) -> NotConfiguredError:
    return NotConfiguredError(
        capability=capability,
        missing=["provider_config", "provider_config_revision"],
        configure_via=configure_via,
    )
