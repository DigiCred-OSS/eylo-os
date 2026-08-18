"""Build organization- and session-scoped WebSocket error responses."""

from fastapi import status

from eylo.common.contracts.websocket import build_ws_error_response
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import WsRequestEvent, WsResponse


async def handle_error(
    event: WsRequestEvent | None,
    ctx: SessionContext,
    message: str | None = None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> WsResponse:
    """Handle error events or create generic error responses."""
    return build_ws_error_response(
        event,
        organization_id=ctx.organization_id,
        session_id=ctx.session_id,
        message=message,
        status_code=status_code,
    )
