"""Capability metadata for the `provider_configs` domain."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.crypto import get_secret_cipher
from eylo.modules.provider_configs.repository import ProviderConfigRepository


@dataclass(frozen=True)
class CapabilityStatus:
    configured: bool
    verified: bool
    ready: bool
    providers: tuple[str, ...]


class CapabilityRegistry:
    """Read capability availability from active shared provider configs only."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_for_organization(
        self,
        organization_id: UUID,
    ) -> dict[Capability, CapabilityStatus]:
        configs = await ProviderConfigRepository(
            self._session,
            get_secret_cipher(),
        ).list_for_organization(organization_id)

        providers = {capability: set() for capability in Capability}
        configured = {capability: False for capability in Capability}
        verified = {capability: False for capability in Capability}
        ready = {capability: False for capability in Capability}
        for config in configs:
            capability = config.capability
            providers[capability].add(config.provider)
            configured[capability] = configured[capability] or config.configured
            verified[capability] = verified[capability] or config.verified
            ready[capability] = ready[capability] or config.ready

        return {
            capability: CapabilityStatus(
                configured=configured[capability],
                verified=verified[capability],
                ready=ready[capability],
                providers=tuple(sorted(providers[capability])),
            )
            for capability in Capability
        }


async def ready_capabilities(
    session: AsyncSession,
    organization_id: UUID,
) -> frozenset[Capability]:
    """Return only capabilities with at least one current ready config."""
    statuses = await CapabilityRegistry(session).get_for_organization(organization_id)
    return frozenset(
        capability for capability, status in statuses.items() if status.ready
    )


__all__ = ["CapabilityRegistry", "CapabilityStatus", "ready_capabilities"]
