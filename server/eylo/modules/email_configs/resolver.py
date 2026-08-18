"""Resolve one explicit organization email config."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.email_configs.domain import InvalidEmailConfig, ResolvedEmail
from eylo.modules.email_configs.service import EmailConfigService
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError

__all__ = ["EmailConfigResolver"]


class EmailConfigResolver:
    def __init__(self, configs: EmailConfigService) -> None:
        self._configs = configs

    async def resolve(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
    ) -> ResolvedEmail:
        if provider_config_id is None:
            raise _not_configured("provider_config")
        provider_config = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        try:
            return ResolvedEmail.from_provider_config(
                provider_config_id=provider_config.provider_config_id,
                organization_id=organization_id,
                provider_config=provider_config,
            )
        except InvalidEmailConfig:
            raise _not_configured("valid_provider_config") from None

    async def resolve_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
    ) -> ResolvedEmail:
        provider_config = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        try:
            return ResolvedEmail.from_provider_config(
                provider_config_id=provider_config.provider_config_id,
                organization_id=organization_id,
                provider_config=provider_config,
            )
        except InvalidEmailConfig:
            raise _not_configured("valid_pinned_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.EMAIL,
        missing=[missing],
        configure_via="/api/email-configs",
    )
