"""HTTP routes for the `auth` domain."""

from fastapi import APIRouter

from eylo.common.database import start_transaction
from eylo.modules.auth.controllers.public_session import (
    PublicSessionController,
    SessionValidationRequest,
    SessionValidationResponse,
)

router = APIRouter(prefix="/public", tags=["Public Session"])


@router.post("/session/validate", response_model=SessionValidationResponse)
async def validate_session(payload: SessionValidationRequest):
    """Validate a session using auth session token and verify all relationships."""
    async with start_transaction() as db:
        controller = PublicSessionController(db)
        return await controller.validate_session(payload)
