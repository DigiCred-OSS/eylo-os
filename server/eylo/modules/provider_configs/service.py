"""Application services for the `provider_configs` domain."""

from collections.abc import Mapping
from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    ProviderConfig,
    ProviderConfigNotFound,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.provider_configs.repository import ProviderConfigRepository


class ProviderConfigService:
    """Provider-config lifecycle use cases within one caller-owned transaction."""

    def __init__(self, repository: ProviderConfigRepository):
        self._repository = repository

    async def create(
        self,
        *,
        organization_id: UUID,
        capability: Capability | str,
        provider: str,
        name: str,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> ProviderConfig:
        provider_config = ProviderConfig.create(
            organization_id=organization_id,
            capability=capability,
            provider=provider,
            name=name,
            config=config,
            secrets=secrets,
        )
        return await self._repository.add(provider_config)

    async def get(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> ProviderConfig:
        provider_config = await self._repository.get(organization_id, config_id)
        if provider_config is None:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        return provider_config

    async def get_for_update(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> ProviderConfig:
        """Lock one owned active config for a caller-owned consistency check."""
        return await self._require_for_update(organization_id, config_id)

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        revision: int,
    ) -> ProviderConfig:
        provider_config = await self._repository.get_revision(
            organization_id,
            config_id,
            revision,
        )
        if provider_config is None:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        return provider_config

    async def list(
        self,
        *,
        organization_id: UUID,
        capability: Capability | None = None,
    ) -> list[ProviderConfig]:
        return await self._repository.list_for_organization(
            organization_id,
            capability,
        )

    async def update(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        name: str | None = None,
        config: Mapping[str, object] | None = None,
        secret_patch: Mapping[str, str | None] | None = None,
    ) -> ProviderConfig:
        provider_config = await self._require_for_update(
            organization_id,
            config_id,
        )
        if config is None and secret_patch is None:
            if name is None:
                return provider_config
            return await self._repository.save(provider_config.rename(name))
        return await self._repository.save(
            provider_config.update(
                name=name,
                config=config,
                secret_patch=secret_patch,
            )
        )

    async def mark_verified(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        expected_revision: int,
        verification_metadata: Mapping[str, object] | None = None,
    ) -> ProviderConfig:
        provider_config = await self._require_for_update(
            organization_id,
            config_id,
        )
        return await self._repository.save(
            provider_config.mark_verified(
                expected_revision=expected_revision,
                verification_metadata=verification_metadata,
            )
        )

    async def set_enabled(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
        enabled: bool,
    ) -> ProviderConfig:
        provider_config = await self._require_for_update(
            organization_id,
            config_id,
        )
        return await self._repository.save(provider_config.set_enabled(enabled))

    async def delete(
        self,
        *,
        organization_id: UUID,
        config_id: UUID,
    ) -> None:
        provider_config = await self._require_for_update(
            organization_id,
            config_id,
        )
        await self._repository.save(provider_config.soft_delete())

    async def resolve_for_new_run(
        self,
        *,
        organization_id: UUID,
        capability: Capability,
        config_id: UUID,
        granted: bool,
        configure_via: str,
    ) -> EffectiveProviderConfig:
        provider_config = await self._repository.get(organization_id, config_id)
        self._require_capability(
            provider_config,
            capability=capability,
            configure_via=configure_via,
        )
        assert provider_config is not None
        if not granted:
            raise _not_configured(
                capability,
                missing="config_grant",
                configure_via=configure_via,
            )
        if not provider_config.enabled:
            raise _not_configured(
                capability,
                missing="enabled_config",
                configure_via=configure_via,
            )
        if not provider_config.verified:
            raise _not_configured(
                capability,
                missing="current_verification",
                configure_via=configure_via,
            )
        if not provider_config.ready:
            raise _not_configured(
                capability,
                missing="ready_config",
                configure_via=configure_via,
            )
        return provider_config.to_effective(granted=True)

    async def resolve_pinned(
        self,
        *,
        organization_id: UUID,
        capability: Capability,
        config_id: UUID,
        revision: int,
        granted: bool,
        configure_via: str,
    ) -> EffectiveProviderConfig:
        provider_config = await self._repository.get_revision(
            organization_id,
            config_id,
            revision,
        )
        self._require_capability(
            provider_config,
            capability=capability,
            configure_via=configure_via,
        )
        assert provider_config is not None
        if not granted:
            raise _not_configured(
                capability,
                missing="config_grant",
                configure_via=configure_via,
            )
        if not provider_config.verified:
            raise _not_configured(
                capability,
                missing="verified_revision",
                configure_via=configure_via,
            )
        return provider_config.to_effective(granted=True)

    async def _require_for_update(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> ProviderConfig:
        provider_config = await self._repository.get_for_update(
            organization_id,
            config_id,
        )
        if provider_config is None:
            raise ProviderConfigNotFound("Provider configuration was not found.")
        return provider_config

    @staticmethod
    def _require_capability(
        provider_config: ProviderConfig | None,
        *,
        capability: Capability,
        configure_via: str,
    ) -> None:
        if provider_config is None or provider_config.capability is not capability:
            raise _not_configured(
                capability,
                missing="provider_config",
                configure_via=configure_via,
            )


def _not_configured(
    capability: Capability,
    *,
    missing: str,
    configure_via: str,
) -> NotConfiguredError:
    return NotConfiguredError(
        capability=capability,
        missing=[missing],
        configure_via=configure_via,
    )
