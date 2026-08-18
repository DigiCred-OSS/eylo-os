"""Compose provider-native and Eylo-owned Voice Config capabilities."""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.voice.schemas.api import (
    VoiceConfig,
    VoiceConfigCompatibilityRead,
    VoicePlatformFeatureRead,
    VoiceProviderCapabilityRead,
)
from eylo.modules.voice.services.voice_configs import VoiceConfigService
from eylo.modules.voice_configs.catalog import RealtimeProviders, VoiceKind
from eylo.modules.voice_configs.domain import ResolvedRealtime
from eylo.modules.voice_configs.wiring import (
    build_voice_config_service as build_provider_voice_config_service,
)
from eylo.sockets.realtime.config import RealtimeSessionConfig
from eylo.sockets.realtime.factory import RealtimeFactory
from eylo.sockets.stt.factory import STTFactory
from eylo.sockets.tts.factory import TTSFactory

_GUIDANCE = (
    "Eylo platform features remain available when a selected provider does not "
    "offer the same behavior natively. Native capabilities describe only the "
    "selected adapter path; provider-specific settings stay in that provider's "
    "configuration."
)


class VoiceCapabilityService:
    """Build a read model without making a vendor network request."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._voice_configs = VoiceConfigService(db)
        self._provider_configs = build_provider_voice_config_service(db)

    async def get(
        self,
        *,
        organization_id: UUID,
        voice_config_id: UUID,
    ) -> VoiceConfigCompatibilityRead:
        voice_config = await self._voice_configs.get(
            organization_id=organization_id,
            voice_config_id=voice_config_id,
        )
        providers: list[VoiceProviderCapabilityRead] = []
        selected = (
            (VoiceKind.STT, voice_config.config.stt_provider_config_id),
            (VoiceKind.TTS, voice_config.config.tts_provider_config_id),
            (VoiceKind.REALTIME, voice_config.config.realtime_provider_config_id),
        )
        for kind, config_id in selected:
            if config_id is None:
                continue
            providers.append(
                await self._provider_capabilities(
                    organization_id=organization_id,
                    kind=kind,
                    config_id=config_id,
                )
            )

        return VoiceConfigCompatibilityRead(
            voice_config_id=voice_config.id,
            voice_config_revision=voice_config.revision,
            platform_features=_platform_features(voice_config.config),
            selected_providers=providers,
            guidance=_GUIDANCE,
        )

    async def _provider_capabilities(
        self,
        *,
        organization_id: UUID,
        kind: VoiceKind,
        config_id: UUID,
    ) -> VoiceProviderCapabilityRead:
        stored = await self._provider_configs.get(
            organization_id=organization_id,
            config_id=config_id,
            kind=kind,
        )
        runtime_config = {**stored.config, **stored.secrets}

        if kind is VoiceKind.STT:
            adapter = STTFactory(
                organization_id=organization_id,
                session_id="voice-config-capability-inspection",
                stt_vendor=stored.provider,
                stt_config=runtime_config,
                api_key=stored.secrets.get("api_key"),
            ).service
            capabilities = asdict(adapter.capabilities)
        elif kind is VoiceKind.TTS:
            adapter = TTSFactory(
                tts_vendor=stored.provider,
                tts_config=runtime_config,
                api_key=stored.secrets.get("api_key"),
            ).service
            capabilities = adapter.capabilities.model_dump(mode="json")
        else:
            capabilities = self._realtime_capabilities(
                organization_id=organization_id,
                provider_config_id=stored.id,
                provider_config_revision=stored.revision,
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )

        return VoiceProviderCapabilityRead(
            kind=kind.value,
            provider_config_id=stored.id,
            provider=stored.provider,
            ready=stored.ready,
            native_capabilities=capabilities,
        )

    @staticmethod
    def _realtime_capabilities(
        *,
        organization_id: UUID,
        provider_config_id: UUID,
        provider_config_revision: int,
        provider: str,
        config,
        secrets,
    ) -> dict:
        resolved = ResolvedRealtime(
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config_revision,
            organization_id=organization_id,
            provider=RealtimeProviders(provider),
            config=config,
            secrets=secrets,
            configured=True,
            verified=False,
            ready=False,
            granted=True,
        )
        session_config = RealtimeSessionConfig.model_validate(
            {
                "organization_id": organization_id,
                "conversation_id": UUID(int=0),
                "agent_id": UUID(int=0),
                "session_id": "voice-config-capability-inspection",
                "vendor": provider,
                "model": config["model"],
                "voice": config["voice"],
                "temperature": config.get("temperature"),
                "top_p": config.get("top_p"),
                "max_tokens": config.get("max_tokens"),
                "input_transcription_model": config.get(
                    "input_transcription_model"
                ),
                "vad_threshold": config.get("vad_threshold"),
                "vad_silence_ms": config.get("vad_silence_ms"),
                "endpointing_sensitivity": config.get(
                    "endpointing_sensitivity"
                ),
                "is_context_compression_enabled": config.get(
                    "context_compression_enabled"
                ),
                "context_compression_trigger_tokens": config.get(
                    "context_compression_trigger_tokens"
                ),
            }
        )
        adapter = RealtimeFactory.create(session_config, resolved)
        return asdict(adapter.capabilities)


def _platform_features(config: VoiceConfig) -> list[VoicePlatformFeatureRead]:
    silence_enabled = (
        config.silence.reminder_max_count > 0
        or config.silence.end_call_after_silence_ms > 0
    )
    return [
        _feature(
            "interruption_handling",
            "Interruption handling",
            True,
            "Eylo coordinates user speech, Agent playback, and interrupted turns.",
        ),
        _feature(
            "silence_policy",
            "Silence policy",
            silence_enabled,
            "Eylo owns reminders and silence-based call termination.",
        ),
        _feature(
            "duration_limit",
            "Duration limit",
            config.conversation_control.max_duration_seconds > 0,
            "Eylo ends the session when its configured duration is reached.",
        ),
        _feature(
            "recording_capture_and_upload",
            "Recording capture and upload",
            config.artifacts.audio_storage_enabled,
            "Eylo records the primary flow and uploads through the selected storage config.",
        ),
        _feature(
            "recording_notification",
            "Recording notification",
            config.compliance.recording_consent_required,
            "Eylo attempts the notification without making it a call gate.",
        ),
        _feature(
            "transcript_persistence",
            "Transcript persistence",
            config.artifacts.transcript_storage_enabled,
            "Eylo persists the canonical post-call transcript.",
        ),
        _feature(
            "post_call_pii_processing",
            "Post-call PII processing",
            config.compliance.redact_pii_in_transcripts,
            "Eylo builds redacted canonical storage after the live flow.",
        ),
        _feature(
            "session_observability",
            "Session observability",
            (
                config.observability.metrics_enabled
                or config.observability.vendor_latency_tracking_enabled
            ),
            "Eylo owns session metrics and provider latency tracking.",
        ),
        _feature(
            "primary_agent_voice_pinning",
            "Primary Agent Voice Config pinning",
            True,
            "Eylo keeps the primary Agent's published Voice Config for all handoffs.",
        ),
    ]


def _feature(
    key: str,
    label: str,
    enabled: bool,
    description: str,
) -> VoicePlatformFeatureRead:
    return VoicePlatformFeatureRead(
        key=key,
        label=label,
        enabled=enabled,
        description=description,
    )
