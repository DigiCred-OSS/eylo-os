"""Structured WebSocket error response builders."""

from uuid import UUID

from fastapi import status

from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.pipelines.websocket.schemas import WsEventAction, WsResponse


def not_configured_response(
    error: NotConfiguredError,
    *,
    organization_id: UUID,
    session_id: str,
    request_id: str | None = None,
) -> WsResponse:
    """Map missing capability details into the WebSocket error envelope."""
    return WsResponse(
        status=status.HTTP_409_CONFLICT,
        kind=WsEventAction.ERROR,
        data={
            "capability": error.capability.value,
            "missing": list(error.missing),
            "configure_via": error.configure_via,
        },
        organization_id=organization_id,
        session_id=session_id,
        request_id=request_id,
    )
