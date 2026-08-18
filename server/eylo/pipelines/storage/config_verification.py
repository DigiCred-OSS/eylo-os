"""Bounded, revision-safe storage provider verification."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from eylo.common.database import start_transaction
from eylo.modules.storage_configs.domain import StorageProviderConfig
from eylo.modules.storage_configs.verification import (
    StorageProviderVerification,
    StorageProviderVerifier,
    StorageVerificationCapabilities,
    StorageVerificationError,
    StorageVerificationResult,
)
from eylo.modules.storage_configs.wiring import build_storage_config_service
from eylo.pipelines.storage.config import build_storage_runtime_config
from eylo.sockets.storage.factory import StorageFactory
from eylo.sockets.storage.s3 import S3StorageAdapter

_VERIFICATION_TIMEOUT_SECONDS = 60.0
_VERIFY_CONTENT = b"eylo-storage-verification"


class StorageRuntimeVerifier:
    """Exercise every operation the selected adapter claims to support."""

    async def verify(
        self,
        config: StorageProviderConfig,
        *,
        organization_id: UUID,
        provider_config_id: UUID,
    ) -> StorageProviderVerification:
        runtime_config = build_storage_runtime_config(
            config,
            organization_id=organization_id,
            provider_config_id=provider_config_id,
        )
        adapter = StorageFactory(runtime_config).get_adapter()
        key = f".eylo-verification/{uuid4()}.txt"
        uploaded = False
        try:
            with tempfile.TemporaryDirectory(prefix="eylo-storage-verify-") as tmp:
                path = Path(tmp) / "probe.txt"
                path.write_bytes(_VERIFY_CONTENT)
                async with asyncio.timeout(_VERIFICATION_TIMEOUT_SECONDS):
                    if isinstance(adapter, S3StorageAdapter):
                        await adapter.head_bucket()
                    await adapter.upload_file(
                        path=path,
                        key=key,
                        content_type="text/plain",
                    )
                    uploaded = True
                    downloaded = await adapter.download_object(
                        key,
                        max_bytes=len(_VERIFY_CONTENT),
                    )
                    if downloaded != _VERIFY_CONTENT:
                        raise StorageVerificationError(
                            "Storage verification read different bytes."
                        )
                    listed = await adapter.list_objects(key, limit=1)
                    if not listed or listed[0].key != key:
                        raise StorageVerificationError(
                            "Storage verification object was not listable."
                        )
                    if adapter.capabilities.presigned_download:
                        await adapter.generate_presigned_url(key, expires_in=60)
                    if not await adapter.delete_object(key):
                        raise StorageVerificationError(
                            "Storage verification object was not deleted."
                        )
                    uploaded = False
        except Exception:
            if uploaded:
                try:
                    await adapter.delete_object(key)
                except Exception:
                    pass
            raise StorageVerificationError(
                "Storage provider verification failed."
            ) from None

        capabilities = adapter.capabilities
        return StorageProviderVerification(
            provider=config.provider.value,
            capabilities=StorageVerificationCapabilities(
                upload=capabilities.upload,
                list=capabilities.list,
                download=capabilities.download,
                delete=capabilities.delete,
                presigned_download=capabilities.presigned_download,
            ),
        )


class StorageConfigVerificationUseCase:
    """Keep provider I/O outside DB transactions, then CAS the revision."""

    def __init__(self, verifier: StorageProviderVerifier) -> None:
        self._verifier = verifier

    async def verify(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> StorageVerificationResult:
        async with start_transaction():
            stored = await build_storage_config_service().get(
                organization_id=organization_id,
                config_id=config_id,
            )
            provider_config = StorageProviderConfig.validate(
                provider=stored.provider,
                config=stored.config,
                secrets=stored.secrets,
            )
            expected_revision = stored.revision

        result = await self._verifier.verify(
            provider_config,
            organization_id=organization_id,
            provider_config_id=config_id,
        )

        async with start_transaction():
            verified = await build_storage_config_service().mark_verified(
                organization_id=organization_id,
                config_id=config_id,
                expected_revision=expected_revision,
            )
        assert verified.verified_at is not None
        return StorageVerificationResult(
            provider=result.provider,
            revision=verified.revision,
            verified_at=verified.verified_at,
            capabilities=result.capabilities,
        )
