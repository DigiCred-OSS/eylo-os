"""HTTP routes for the `websocket` pipeline."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, WebSocket

from eylo.pipelines.websocket.controllers import (
    WebSocketController,
    get_websocket_controller,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])


@router.websocket("/{organization_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    organization_id: UUID,
    session_id: str,
    user_session_id: UUID | None = Query(default=None),
    request: Request = None,
    controller: WebSocketController = Depends(get_websocket_controller),
):
    """WebSocket endpoint that delegates connection handling to a controller."""
    await controller.handle_connection(
        websocket=websocket,
        organization_id=organization_id,
        session_id=session_id,
        requested_user_session_id=user_session_id,
        request=request,
    )
