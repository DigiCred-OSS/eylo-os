"""Bounded, revision-safe STT/TTS provider verification."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.voice_configs.catalog import (
    RealtimeProviders,
    VoiceKind,
)
from eylo.modules.voice_configs.domain import ResolvedRealtime, VoiceProviderConfig
from eylo.modules.voice_configs.verification import (
    VoiceProviderVerification,
    VoiceProviderVerifier,
    VoiceVerificationError,
    VoiceVerificationResult,
)
from eylo.modules.voice_configs.wiring import build_voice_config_service
from eylo.sockets.realtime.config import RealtimeSessionConfig
from eylo.sockets.realtime.factory import RealtimeFactory
from eylo.sockets.stt.factory import STTFactory
from eylo.sockets.tts.factory import TTSFactory

_VERIFICATION_TIMEOUT_SECONDS = 20.0
logger = logging.getLogger(__name__)


class VoiceRuntimeVerifier:
    """Construct and connect the same socket adapter used by live voice."""

    async def verify(
        self,
        config: VoiceProviderConfig,
    ) -> VoiceProviderVerification:
        try:
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                if config.kind is VoiceKind.STT:
                    await self._verify_stt(config)
                elif config.kind is VoiceKind.TTS:
                    await self._verify_tts(config)
                else:
                    await self._verify_realtime(config)
        except Exception as error:
            logger.warning(
                "Voice provider verification failed kind=%s provider=%s "
                "error_type=%s",
                config.kind.value,
                config.provider.value,
                type(error).__name__,
            )
            raise VoiceVerificationError(
                "Voice provider verification failed."
            ) from None
        return VoiceProviderVerification(
            provider=config.provider.value,
            kind=config.kind,
        )

    @staticmethod
    async def _verify_stt(config: VoiceProviderConfig) -> None:
        factory = STTFactory(
            organization_id=UUID(int=0),
            session_id="provider-config-verification",
            stt_vendor=config.provider.value,
            stt_config={**config.config, **config.secrets},
            api_key=config.secrets.get("api_key"),
        )
        async with factory.connection():
            if not factory.is_connected:
                raise VoiceVerificationError(
                    "Voice provider verification failed."
                )

    @staticmethod
    async def _verify_tts(config: VoiceProviderConfig) -> None:
        runtime_config = {**config.config, **config.secrets}
        factory = TTSFactory(
            tts_vendor=config.provider.value,
            tts_config=runtime_config,
            api_key=config.secret,
        )
        async with factory.connection():
            if not factory.service.is_connected:
                raise VoiceVerificationError(
                    "Voice provider verification failed."
                )

    @staticmethod
    async def _verify_realtime(config: VoiceProviderConfig) -> None:
        if not isinstance(config.provider, RealtimeProviders):
            raise VoiceVerificationError("Voice provider verification failed.")
        resolved = ResolvedRealtime(
            provider_config_id=UUID(int=0),
            provider_config_revision=1,
            organization_id=UUID(int=0),
            provider=config.provider,
            config=config.config,
            secrets=config.secrets,
            configured=True,
            verified=False,
            ready=False,
            granted=True,
        )
        session_config = RealtimeSessionConfig.model_validate(
            {
                "organization_id": UUID(int=0),
                "conversation_id": UUID(int=0),
                "agent_id": UUID(int=0),
                "session_id": "provider-config-verification",
                "vendor": config.provider.value,
                "model": config.config["model"],
                "voice": config.config["voice"],
                "temperature": config.config.get("temperature"),
                "top_p": config.config.get("top_p"),
                "max_tokens": config.config.get("max_tokens"),
                "input_transcription_model": config.config.get(
                    "input_transcription_model"
                ),
                "vad_threshold": config.config.get("vad_threshold"),
                "vad_silence_ms": config.config.get("vad_silence_ms"),
                "endpointing_sensitivity": config.config.get(
                    "endpointing_sensitivity"
                ),
                "is_context_compression_enabled": config.config.get(
                    "context_compression_enabled"
                ),
                "context_compression_trigger_tokens": config.config.get(
                    "context_compression_trigger_tokens"
                ),
            }
        )
        adapter = RealtimeFactory.create(session_config, resolved)
        try:
            await adapter.connect()
            await adapter.verify_ready()
        finally:
            await adapter.disconnect()


class VoiceConfigVerificationUseCase:
    """Keep the external check outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: VoiceProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        kind: VoiceKind,
    ) -> VoiceVerificationResult:
        async with start_transaction():
            stored = await build_voice_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
                kind=kind,
            )
            provider_config = VoiceProviderConfig.validate(
                provider=stored.provider,
                kind=kind,
                config=stored.config,
                secrets=stored.secrets,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(provider_config)

        async with start_transaction():
            verified = await build_voice_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
            )
        assert verified.verified_at is not None
        return VoiceVerificationResult(
            provider=result.provider,
            kind=result.kind,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )
