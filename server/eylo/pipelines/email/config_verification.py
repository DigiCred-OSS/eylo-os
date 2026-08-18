"""Bounded, revision-safe email provider verification."""

from __future__ import annotations

import asyncio
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.email_configs.domain import EmailProviderConfig
from eylo.modules.email_configs.verification import (
    EmailProviderVerification,
    EmailProviderVerifier,
    EmailVerificationError,
    EmailVerificationResult,
)
from eylo.modules.email_configs.wiring import build_email_config_service
from eylo.pipelines.email.config import build_email_runtime_config
from eylo.sockets.email.factory import EmailFactory

_VERIFICATION_TIMEOUT_SECONDS = 60.0


class EmailRuntimeVerifier:
    """Authenticate through the same adapter used for email delivery."""

    async def verify(
        self,
        config: EmailProviderConfig,
    ) -> EmailProviderVerification:
        try:
            runtime_config = build_email_runtime_config(config)
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                await EmailFactory(runtime_config).get_adapter().verify_credentials()
        except Exception:
            raise EmailVerificationError(
                "Email provider verification failed."
            ) from None
        return EmailProviderVerification(provider=config.provider.value)


class EmailConfigVerificationUseCase:
    """Keep external auth outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: EmailProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> EmailVerificationResult:
        async with start_transaction():
            stored = await build_email_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
            )
            provider_config = EmailProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(provider_config)

        async with start_transaction():
            verified = await build_email_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
            )
        assert verified.verified_at is not None
        return EmailVerificationResult(
            provider=result.provider,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )
