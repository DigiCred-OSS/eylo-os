"""HTTP routes for the `auth` domain."""

from fastapi import APIRouter, Depends

from eylo.common.database import start_transaction
from eylo.modules.auth.controllers import AuthController
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.members.schemas.api import (
    MemberApiResponseSchema,
)

router = APIRouter(tags=["auth"], prefix="/auth")


@router.get("/me", response_model=MemberApiResponseSchema)
async def get_me(current_user=Depends(get_current_user)) -> MemberApiResponseSchema:
    """Get Current User Profile."""
    async with start_transaction(ro=True):
        return await AuthController().get_me(current_user)
