"""AWS S3 adapter using explicit credentials and an SDK-derived endpoint."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import aioboto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from eylo.sockets.storage.base import (
    StorageCapabilities,
    StorageObjectTooLarge,
    StorageOperationError,
    StorageVendorAdapter,
    StoredObject,
    validate_content_sha256,
    validate_expiry,
    validate_key,
    validate_limit,
)
from eylo.sockets.storage.schemas import S3StorageConfig

logger = logging.getLogger(__name__)


class S3StorageAdapter(StorageVendorAdapter):
    """AWS S3 operations for one bucket and explicit credential set."""

    capabilities = StorageCapabilities(
        presigned_download=True,
        stable_key_put=True,
        put_reconciliation=True,
    )

    def __init__(self, config: S3StorageConfig) -> None:
        self.config = config
        self._key_prefix = validate_key(config.key_prefix)
        self._session = aioboto3.Session(
            aws_access_key_id=config.access_key_id.get_secret_value(),
            aws_secret_access_key=config.secret_access_key.get_secret_value(),
            aws_session_token=(
                config.session_token.get_secret_value()
                if config.session_token is not None
                else None
            ),
            region_name=config.region,
        )
        self._client_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        )

    def _client(self):
        return self._session.client("s3", config=self._client_config)

    def _object_key(self, key: str, *, allow_empty: bool = False) -> str:
        logical_key = validate_key(key, allow_empty=allow_empty)
        if not logical_key:
            return f"{self._key_prefix}/"
        return f"{self._key_prefix}/{logical_key}"

    def _logical_key(self, object_key: str) -> str | None:
        prefix = f"{self._key_prefix}/"
        if not object_key.startswith(prefix):
            return None
        try:
            return validate_key(object_key.removeprefix(prefix))
        except StorageOperationError:
            return None

    async def upload_file(
        self,
        *,
        path: Path,
        key: str,
        content_type: str = "application/octet-stream",
        content_sha256: str | None = None,
    ) -> str:
        logical_key = validate_key(key)
        object_key = self._object_key(logical_key)
        expected_digest = validate_content_sha256(content_sha256)
        if expected_digest is not None:
            try:
                actual_digest = await asyncio.to_thread(_sha256_path, path)
            except OSError:
                raise StorageOperationError(
                    "upload_source_read",
                    retryable=False,
                ) from None
            if actual_digest != expected_digest:
                raise StorageOperationError(
                    "upload_content_digest_mismatch",
                    retryable=False,
                )
        extra_args = {"ContentType": content_type}
        if expected_digest is not None:
            extra_args["Metadata"] = {"eylo-sha256": expected_digest}
        try:
            async with self._client() as s3:
                await s3.upload_file(
                    str(path),
                    self.config.bucket,
                    object_key,
                    ExtraArgs=extra_args,
                )
        except (BotoCoreError, ClientError, OSError) as error:
            raise _storage_error(error, operation="upload") from None
        return self.build_object_url(logical_key)

    async def inspect_object(self, key: str) -> StoredObject | None:
        logical_key = validate_key(key)
        object_key = self._object_key(logical_key)
        try:
            async with self._client() as s3:
                response = await s3.head_object(
                    Bucket=self.config.bucket,
                    Key=object_key,
                )
        except ClientError as error:
            if _is_missing(error):
                return None
            raise _storage_error(error, operation="inspect") from None
        except BotoCoreError as error:
            raise _storage_error(error, operation="inspect") from None
        metadata = response.get("Metadata") or {}
        content_sha256 = metadata.get("eylo-sha256")
        return StoredObject(
            key=logical_key,
            size=int(response.get("ContentLength", 0)),
            content_sha256=(
                validate_content_sha256(content_sha256)
                if content_sha256 is not None
                else None
            ),
        )

    async def list_objects(
        self,
        prefix: str,
        *,
        limit: int = 1000,
    ) -> list[StoredObject]:
        logical_prefix = validate_key(prefix, allow_empty=True)
        object_prefix = self._object_key(logical_prefix, allow_empty=True)
        ceiling = validate_limit(limit)
        found: list[StoredObject] = []
        try:
            async with self._client() as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(
                    Bucket=self.config.bucket,
                    Prefix=object_prefix,
                    PaginationConfig={"MaxItems": ceiling},
                ):
                    for entry in page.get("Contents", []):
                        object_key = str(entry["Key"])
                        if object_key.endswith("/"):
                            continue
                        key = self._logical_key(object_key)
                        if key is None:
                            continue
                        found.append(
                            StoredObject(key=key, size=int(entry.get("Size", 0)))
                        )
        except (BotoCoreError, ClientError) as error:
            raise _storage_error(error, operation="list") from None
        return found[:ceiling]

    async def download_object(
        self,
        key: str,
        *,
        max_bytes: int | None = None,
    ) -> bytes | None:
        object_key = self._object_key(key)
        if max_bytes is not None and (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or max_bytes < 1
        ):
            raise StorageOperationError("invalid_size_limit", retryable=False)
        extra = {"Range": f"bytes=0-{max_bytes}"} if max_bytes is not None else {}
        try:
            async with self._client() as s3:
                response = await s3.get_object(
                    Bucket=self.config.bucket,
                    Key=object_key,
                    **extra,
                )
                body = await response["Body"].read()
        except ClientError as error:
            if _is_missing(error):
                return None
            raise _storage_error(error, operation="download") from None
        except BotoCoreError as error:
            raise _storage_error(error, operation="download") from None
        if max_bytes is not None and len(body) > max_bytes:
            raise StorageObjectTooLarge
        return body

    async def stream_object(
        self,
        key: str,
        *,
        chunk_size: int = 64 * 1024,
    ) -> AsyncIterator[bytes]:
        """Stream S3 bytes while keeping the client and response body alive."""
        if (
            isinstance(chunk_size, bool)
            or not isinstance(chunk_size, int)
            or not 1 <= chunk_size <= 8 * 1024 * 1024
        ):
            raise StorageOperationError("invalid_chunk_size", retryable=False)
        object_key = self._object_key(key)
        try:
            async with self._client() as s3:
                try:
                    response = await s3.get_object(
                        Bucket=self.config.bucket,
                        Key=object_key,
                    )
                except ClientError as error:
                    if _is_missing(error):
                        return
                    raise _storage_error(error, operation="download") from None
                body = response["Body"]
                try:
                    while chunk := await body.read(chunk_size):
                        yield bytes(chunk)
                finally:
                    closed = body.close()
                    if inspect.isawaitable(closed):
                        await closed
        except StorageOperationError:
            raise
        except (BotoCoreError, ClientError, OSError) as error:
            raise _storage_error(error, operation="download") from None

    async def delete_object(self, key: str) -> bool:
        object_key = self._object_key(key)
        try:
            async with self._client() as s3:
                await s3.delete_object(Bucket=self.config.bucket, Key=object_key)
        except (BotoCoreError, ClientError) as error:
            raise _storage_error(error, operation="delete") from None
        return True

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        object_key = self._object_key(key)
        expiry = validate_expiry(expires_in)
        try:
            async with self._client() as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.config.bucket, "Key": object_key},
                    ExpiresIn=expiry,
                )
        except (BotoCoreError, ClientError) as error:
            raise _storage_error(error, operation="presign") from None

    async def head_bucket(self) -> None:
        try:
            async with self._client() as s3:
                await s3.head_bucket(Bucket=self.config.bucket)
        except (BotoCoreError, ClientError) as error:
            raise _storage_error(error, operation="verify") from None

    def build_object_url(self, key: str) -> str:
        object_key = self._object_key(key)
        return (
            f"https://{self.config.bucket}.s3.{self.config.region}.amazonaws.com/"
            f"{object_key}"
        )


def _is_missing(error: ClientError) -> bool:
    code = str(error.response.get("Error", {}).get("Code", ""))
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"NoSuchKey", "NotFound", "404"} or status == 404


def _storage_error(error: Exception, *, operation: str) -> StorageOperationError:
    retryable = isinstance(error, BotoCoreError)
    code = "transport"
    if isinstance(error, ClientError):
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        provider_code = str(error.response.get("Error", {}).get("Code", ""))
        retryable = status == 429 or bool(status and status >= 500)
        if status in {401, 403} or provider_code in {
            "AccessDenied",
            "ExpiredToken",
            "InvalidAccessKeyId",
            "SignatureDoesNotMatch",
        }:
            code = "authentication"
        elif retryable:
            code = "provider_unavailable"
        else:
            code = "provider_rejected"
    logger.warning("S3 %s failed with code=%s", operation, code)
    return StorageOperationError(f"{operation}_{code}", retryable=retryable)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
