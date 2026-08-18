"""Bounded, revision-safe WebRTC provider verification."""

from __future__ import annotations

import asyncio
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.webrtc_configs.domain import WebRTCProviderConfig
from eylo.modules.webrtc_configs.verification import (
    WebRTCProviderVerification,
    WebRTCProviderVerifier,
    WebRTCVerificationError,
    WebRTCVerificationResult,
)
from eylo.modules.webrtc_configs.wiring import build_webrtc_config_service
from eylo.pipelines.webrtc.config import build_stun_turn_config
from eylo.sockets.stun_turn.factory import StunTurnFactory

_VERIFICATION_TIMEOUT_SECONDS = 20.0


class WebRTCRuntimeVerifier:
    """Fetch credentials through the same typed adapter used by live WebRTC."""

    async def verify(
        self,
        config: WebRTCProviderConfig,
    ) -> WebRTCProviderVerification:
        try:
            typed_config = build_stun_turn_config(config)
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                await StunTurnFactory(typed_config).get_ice_servers()
        except Exception:
            raise WebRTCVerificationError(
                "WebRTC provider verification failed."
            ) from None
        return WebRTCProviderVerification(provider=config.provider.value)


class WebRTCConfigVerificationUseCase:
    """Keep the external check outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: WebRTCProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> WebRTCVerificationResult:
        async with start_transaction():
            stored = await build_webrtc_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
            )
            provider_config = WebRTCProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(provider_config)

        async with start_transaction():
            verified = await build_webrtc_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
            )
        assert verified.verified_at is not None
        return WebRTCVerificationResult(
            provider=result.provider,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )
