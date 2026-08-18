"""HTTP routes for the `provider_configs` domain."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends

from eylo.common.database import get_transaction, start_transaction
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.provider_configs.capabilities import CapabilityRegistry
from eylo.modules.provider_configs.controllers import CapabilityController
from eylo.modules.provider_configs.schemas import CapabilitiesResponse

router = APIRouter(tags=["capabilities"])


async def get_capability_controller() -> AsyncIterator[CapabilityController]:
    async with start_transaction(ro=True):
        yield CapabilityController(CapabilityRegistry(get_transaction()))


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    controller: Annotated[
        CapabilityController,
        Depends(get_capability_controller, scope="function"),
    ],
) -> CapabilitiesResponse:
    return await controller.get_for_organization(current_user.organization_id)
