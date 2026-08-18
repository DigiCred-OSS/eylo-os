"""Translate validated platform storage values into typed socket configs."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from eylo.modules.storage_configs.catalog import StorageProviders
from eylo.modules.storage_configs.domain import (
    InvalidStorageConfig,
    ResolvedStorage,
    StorageProviderConfig,
)
from eylo.sockets.storage.schemas import (
    FilesystemStorageConfig,
    S3StorageConfig,
    StorageConfig,
)

FILESYSTEM_ROOT_SETTING = "STORAGE_FILESYSTEM_ROOT"


def build_storage_runtime_config(
    config: StorageProviderConfig | ResolvedStorage,
    *,
    organization_id: UUID,
    provider_config_id: UUID,
    trusted_filesystem_root: Path | None = None,
) -> StorageConfig:
    _require_matching_scope(
        config,
        organization_id=organization_id,
        provider_config_id=provider_config_id,
    )
    values = dict(config.config)
    storage_prefix = _storage_prefix(organization_id, provider_config_id)
    try:
        if config.provider is StorageProviders.S3:
            return S3StorageConfig(
                bucket=values["bucket"],
                region=values["region"],
                key_prefix=storage_prefix,
                access_key_id=config.secret("access_key_id"),
                secret_access_key=config.secret("secret_access_key"),
                session_token=(
                    config.secret("session_token")
                    if "session_token" in config.secrets
                    else None
                ),
            )
        if config.provider is StorageProviders.FILESYSTEM:
            platform_root = (
                trusted_filesystem_root or _configured_filesystem_root()
            ).resolve()
            namespace_root = (
                platform_root
                / str(values["namespace"])
                / Path(storage_prefix)
            ).resolve()
            if not namespace_root.is_relative_to(platform_root):
                raise InvalidStorageConfig(
                    "Filesystem namespace escapes the trusted storage root."
                )
            return FilesystemStorageConfig(root=namespace_root)
    except (KeyError, ValidationError):
        raise InvalidStorageConfig(
            f"Invalid runtime config for {config.provider.value}."
        ) from None
    raise InvalidStorageConfig(f"Unsupported storage provider: {config.provider}")


def _storage_prefix(organization_id: UUID, provider_config_id: UUID) -> str:
    return (
        f"organizations/{organization_id}/"
        f"storage-configs/{provider_config_id}"
    )


def _require_matching_scope(
    config: StorageProviderConfig | ResolvedStorage,
    *,
    organization_id: UUID,
    provider_config_id: UUID,
) -> None:
    if not isinstance(config, ResolvedStorage):
        return
    if (
        config.organization_id != organization_id
        or config.provider_config_id != provider_config_id
    ):
        raise InvalidStorageConfig(
            "Resolved storage config does not match the requested authority."
        )


def _configured_filesystem_root() -> Path:
    from eylo.common.config import settings

    raw = settings.STORAGE_FILESYSTEM_ROOT
    if not raw:
        raise InvalidStorageConfig(
            f"filesystem storage requires operator setting {FILESYSTEM_ROOT_SETTING}."
        )
    root = Path(raw).expanduser()
    if not root.is_absolute() or root == Path(root.anchor):
        raise InvalidStorageConfig(
            f"{FILESYSTEM_ROOT_SETTING} must be a scoped absolute path."
        )
    return root.resolve()
