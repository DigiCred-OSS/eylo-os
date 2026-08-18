"""Persistence access for the `provider_configs` domain."""

import logging
from typing import NoReturn
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.crypto import (
    EncryptionContext,
    SecretCipher,
    SecretDecryptionError,
)
from eylo.modules.provider_configs.domain import (
    ProviderConfig,
    ProviderConfigConflict,
    ProviderConfigNotFound,
    ProviderConfigRevisionConflict,
)
from eylo.modules.provider_configs.models import (
    ProviderConfigModel,
    ProviderConfigRevisionModel,
)

_UNIQUE_CONSTRAINTS = {
    "uq_provider_configs_org_capability_name_active",
    "uq_provider_configs_org_capability_default_active",
}
_REVISION_CONSTRAINT = "uq_provider_config_revisions_config_revision"

logger = logging.getLogger(__name__)


class ProviderConfigRepository:
    """Org-scoped config headers with immutable encrypted revision material."""

    def __init__(self, session: AsyncSession, cipher: SecretCipher):
        self._session = session
        self._cipher = cipher

    async def add(self, config: ProviderConfig) -> ProviderConfig:
        encrypted_secrets = self._encrypt_secrets(config)
        row = ProviderConfigModel(
            id=config.id,
            organization_id=config.organization_id,
            capability=config.capability,
            provider=config.provider,
            name=config.name,
            config=dict(config.config),
            encrypted_secrets=encrypted_secrets,
            revision=config.revision,
            enabled=config.enabled,
            deleted=config.deleted,
        )
        revision = ProviderConfigRevisionModel(
            organization_id=config.organization_id,
            provider_config_id=config.id,
            revision=config.revision,
            config=dict(config.config),
            encrypted_secrets=encrypted_secrets,
            verified_at=config.verified_at,
            verification_metadata=dict(config.verification_metadata),
        )
        self._session.add_all((row, revision))
        await self._flush_with_conflict_mapping()
        return config

    async def get(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> ProviderConfig | None:
        rows = await self._find_rows(organization_id, config_id)
        return self._to_domain(*rows) if rows else None

    async def get_revision(
        self,
        organization_id: UUID,
        config_id: UUID,
        revision: int,
    ) -> ProviderConfig | None:
        rows = await self._find_rows(
            organization_id,
            config_id,
            revision=revision,
        )
        return self._to_domain(*rows) if rows else None

    async def get_for_update(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> ProviderConfig | None:
        rows = await self._find_rows(organization_id, config_id, lock=True)
        return self._to_domain(*rows) if rows else None

    async def list_for_organization(
        self,
        organization_id: UUID,
        capability: Capability | None = None,
    ) -> list[ProviderConfig]:
        query = (
            self._current_revision_query()
            .where(
                ProviderConfigModel.organization_id == organization_id,
                ProviderConfigModel.deleted.is_(False),
            )
            .order_by(
                ProviderConfigModel.capability,
                ProviderConfigModel.name,
                ProviderConfigModel.id,
            )
        )
        if capability is not None:
            query = query.where(ProviderConfigModel.capability == capability)
        rows = (await self._session.execute(query)).all()
        configs: list[ProviderConfig] = []
        for config, revision in rows:
            try:
                configs.append(self._to_domain(config, revision))
            except SecretDecryptionError:
                logger.warning(
                    "Provider credentials are unavailable config=%s "
                    "organization=%s capability=%s revision=%s",
                    config.id,
                    config.organization_id,
                    config.capability,
                    revision.revision,
                )
                configs.append(self._to_unavailable_domain(config, revision))
        return configs

    async def save(self, config: ProviderConfig) -> ProviderConfig:
        persisted_revision = await self._current_revision_for_update(
            config.organization_id,
            config.id,
        )
        if persisted_revision is None:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        if config.revision < persisted_revision:
            raise ProviderConfigRevisionConflict(
                "Provider configuration revision is stale."
            )

        if config.revision > persisted_revision:
            await self._append_revision(config, persisted_revision)
        else:
            await self._update_revision_verification(config)

        await self._update_header(config, persisted_revision)
        await self._flush_with_conflict_mapping()
        return config

    def _current_revision_query(self):
        return select(ProviderConfigModel, ProviderConfigRevisionModel).join(
            ProviderConfigRevisionModel,
            and_(
                ProviderConfigRevisionModel.provider_config_id
                == ProviderConfigModel.id,
                ProviderConfigRevisionModel.organization_id
                == ProviderConfigModel.organization_id,
                ProviderConfigRevisionModel.revision == ProviderConfigModel.revision,
            ),
        )

    async def _find_rows(
        self,
        organization_id: UUID,
        config_id: UUID,
        *,
        revision: int | None = None,
        lock: bool = False,
    ) -> tuple[ProviderConfigModel, ProviderConfigRevisionModel] | None:
        selected_revision = (
            ProviderConfigModel.revision if revision is None else revision
        )
        query = (
            select(ProviderConfigModel, ProviderConfigRevisionModel)
            .join(
                ProviderConfigRevisionModel,
                and_(
                    ProviderConfigRevisionModel.provider_config_id
                    == ProviderConfigModel.id,
                    ProviderConfigRevisionModel.organization_id
                    == ProviderConfigModel.organization_id,
                    ProviderConfigRevisionModel.revision == selected_revision,
                ),
            )
            .where(
                ProviderConfigModel.id == config_id,
                ProviderConfigModel.organization_id == organization_id,
                ProviderConfigModel.deleted.is_(False),
            )
        )
        if lock:
            query = query.with_for_update(of=ProviderConfigModel)
        row = (await self._session.execute(query)).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def _current_revision_for_update(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> int | None:
        query = (
            select(ProviderConfigModel.revision)
            .where(
                ProviderConfigModel.id == config_id,
                ProviderConfigModel.organization_id == organization_id,
                ProviderConfigModel.deleted.is_(False),
            )
            .with_for_update()
        )
        return (await self._session.execute(query)).scalar_one_or_none()

    async def _append_revision(
        self,
        config: ProviderConfig,
        persisted_revision: int,
    ) -> None:
        if config.revision != persisted_revision + 1:
            raise ProviderConfigRevisionConflict(
                "Provider configuration revision sequence is invalid."
            )
        self._session.add(
            ProviderConfigRevisionModel(
                organization_id=config.organization_id,
                provider_config_id=config.id,
                revision=config.revision,
                config=dict(config.config),
                encrypted_secrets=self._encrypt_secrets(config),
                verified_at=config.verified_at,
                verification_metadata=dict(config.verification_metadata),
            )
        )

    async def _update_revision_verification(self, config: ProviderConfig) -> None:
        result = await self._session.execute(
            update(ProviderConfigRevisionModel)
            .where(
                ProviderConfigRevisionModel.organization_id
                == config.organization_id,
                ProviderConfigRevisionModel.provider_config_id == config.id,
                ProviderConfigRevisionModel.revision == config.revision,
            )
            .values(
                verified_at=config.verified_at,
                verification_metadata=dict(config.verification_metadata),
            )
        )
        if result.rowcount != 1:
            raise ProviderConfigRevisionConflict(
                "Provider configuration revision was not found."
            )

    async def _update_header(
        self,
        config: ProviderConfig,
        persisted_revision: int,
    ) -> None:
        values = {
            "capability": config.capability,
            "provider": config.provider,
            "name": config.name,
            "config": dict(config.config),
            "encrypted_secrets": self._encrypt_secrets(config),
            "revision": config.current_revision,
            "enabled": config.enabled,
            "deleted": config.deleted,
        }
        try:
            result = await self._session.execute(
                update(ProviderConfigModel)
                .where(
                    ProviderConfigModel.id == config.id,
                    ProviderConfigModel.organization_id == config.organization_id,
                    ProviderConfigModel.revision == persisted_revision,
                    ProviderConfigModel.deleted.is_(False),
                )
                .values(**values)
            )
        except IntegrityError as error:
            _raise_mapped_integrity_error(error)
        if result.rowcount != 1:
            raise ProviderConfigRevisionConflict(
                "Provider configuration changed during update."
            )

    def _to_domain(
        self,
        row: ProviderConfigModel,
        revision: ProviderConfigRevisionModel,
    ) -> ProviderConfig:
        capability = Capability(row.capability)
        secrets = self._cipher.decrypt(
            revision.encrypted_secrets,
            _encryption_context(
                row.organization_id,
                row.id,
                capability,
                revision.revision,
            ),
        )
        return ProviderConfig(
            id=row.id,
            organization_id=row.organization_id,
            capability=capability,
            provider=row.provider,
            name=row.name,
            config=revision.config,
            secrets=secrets,
            deleted=row.deleted,
            revision=revision.revision,
            current_revision=row.revision,
            enabled=row.enabled,
            verified_at=revision.verified_at,
            verification_metadata=revision.verification_metadata,
        )

    @staticmethod
    def _to_unavailable_domain(
        row: ProviderConfigModel,
        revision: ProviderConfigRevisionModel,
    ) -> ProviderConfig:
        """Project safe list metadata without pretending credentials work."""
        return ProviderConfig(
            id=row.id,
            organization_id=row.organization_id,
            capability=Capability(row.capability),
            provider=row.provider,
            name=row.name,
            config=revision.config,
            secrets={},
            deleted=row.deleted,
            revision=revision.revision,
            current_revision=row.revision,
            enabled=row.enabled,
            verified_at=revision.verified_at,
            verification_metadata=revision.verification_metadata,
            credentials_available=False,
        )

    def _encrypt_secrets(self, config: ProviderConfig) -> str:
        return self._cipher.encrypt(
            config.secrets,
            _encryption_context(
                config.organization_id,
                config.id,
                config.capability,
                config.revision,
            ),
        )

    async def _flush_with_conflict_mapping(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as error:
            _raise_mapped_integrity_error(error)


def _raise_mapped_integrity_error(error: IntegrityError) -> NoReturn:
    constraint = _constraint_name(error)
    if constraint == _REVISION_CONSTRAINT:
        raise ProviderConfigRevisionConflict(
            "Provider configuration revision already exists."
        ) from error
    if constraint in _UNIQUE_CONSTRAINTS:
        raise ProviderConfigConflict(
            "An active provider configuration already uses this name or default."
        ) from error
    raise error


def _encryption_context(
    organization_id: UUID,
    config_id: UUID,
    capability: Capability,
    revision: int,
) -> EncryptionContext:
    return EncryptionContext(
        organization_id=organization_id,
        config_id=config_id,
        capability=capability.value,
        revision=revision,
    )


def _constraint_name(error: IntegrityError) -> str | None:
    cause = getattr(error.orig, "__cause__", None)
    return getattr(cause, "constraint_name", None) or getattr(
        error.orig,
        "constraint_name",
        None,
    )
