"""Authenticated outbound voice-call routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.modules.telephony.voice_controller import VoiceController

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])

controller = VoiceController()


@router.post("/outbound")
async def outbound_call(
    request: Request,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
):
    """Initiates an outbound call via the configured telephony provider.

    This endpoint is used by the outbound_call system tool to trigger calls.
    It expects a JSON body with:
    - to_number: Target phone number
    - agent_id: UUID of the agent
    - initial_message: Optional first message
    """
    return await controller.outbound_call(
        request,
        current_user.organization_id,
        idempotency_key,
    )
