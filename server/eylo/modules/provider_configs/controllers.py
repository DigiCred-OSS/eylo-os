"""Transport orchestration for the `provider_configs` domain."""

from uuid import UUID

from eylo.modules.provider_configs.capabilities import CapabilityRegistry
from eylo.modules.provider_configs.schemas import (
    CapabilitiesResponse,
    CapabilityStatusResponse,
)


class CapabilityController:
    """Map capability read-model results to the transport response."""

    def __init__(self, registry: CapabilityRegistry):
        self._registry = registry

    async def get_for_organization(
        self,
        organization_id: UUID,
    ) -> CapabilitiesResponse:
        statuses = await self._registry.get_for_organization(organization_id)
        return CapabilitiesResponse.model_validate(
            {
                capability.value: CapabilityStatusResponse(
                    configured=status.configured,
                    verified=status.verified,
                    ready=status.ready,
                    providers=list(status.providers),
                )
                for capability, status in statuses.items()
            }
        )
