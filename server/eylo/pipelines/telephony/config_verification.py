"""Bounded, revision-safe telephony provider verification."""

from __future__ import annotations

import asyncio
import hashlib
from uuid import UUID

from eylo.common.database import start_transaction
from eylo.modules.telephony.provider_config_domain import TelephonyProviderConfig
from eylo.modules.telephony.provider_config_verification import (
    TelephonyProviderVerification,
    TelephonyProviderVerifier,
    TelephonyVerificationError,
    TelephonyVerificationResult,
)
from eylo.modules.telephony.wiring import build_telephony_config_service
from eylo.sockets.telephony.verification import TelephonyCredentialProbe

_VERIFICATION_TIMEOUT_SECONDS = 20.0


class TelephonyRuntimeVerifier:
    """Construct the live adapter and authenticate through a read-only endpoint."""

    def __init__(self, probe: TelephonyCredentialProbe | None = None) -> None:
        self._probe = probe or TelephonyCredentialProbe()

    async def verify(
        self,
        config: TelephonyProviderConfig,
    ) -> TelephonyProviderVerification:
        try:
            async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS + 1):
                result = await self._probe.verify(
                    provider=config.provider.value,
                    settings=config.adapter_settings(),
                    timeout_seconds=_VERIFICATION_TIMEOUT_SECONDS,
                )
        except Exception as error:
            raise TelephonyVerificationError(
                "Telephony provider verification failed."
            ) from error
        fingerprint = hashlib.sha256(result.account_reference.encode()).hexdigest()[:16]
        return TelephonyProviderVerification(
            provider=result.provider,
            metadata={
                "account_fingerprint": fingerprint,
                "operation": "read_only_account_lookup",
            },
        )


class TelephonyConfigVerificationUseCase:
    """Keep external auth outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: TelephonyProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> TelephonyVerificationResult:
        async with start_transaction():
            stored = await build_telephony_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
            )
            provider_config = TelephonyProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(provider_config)

        async with start_transaction():
            verified = await build_telephony_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
                verification_metadata=result.metadata,
            )
        assert verified.verified_at is not None
        return TelephonyVerificationResult(
            provider=result.provider,
            revision=verified.revision,
            verified_at=verified.verified_at,
        )
