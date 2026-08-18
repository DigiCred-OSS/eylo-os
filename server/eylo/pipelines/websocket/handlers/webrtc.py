"""Authenticated WebRTC signaling commands."""

from typing import Any, Optional

from fastapi import status

from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.voice.browser import terminate_browser_voice
from eylo.pipelines.webrtc.signaling_manager import (
    WEBRTC_PROTOCOL_VERSION,
    WebRTCSignalingError,
)
from eylo.pipelines.webrtc.singleton import S_webrtc_signaling
from eylo.pipelines.websocket.schemas import (
    WsEventAction,
    WsRequestEvent,
    WsResponse,
)

from .log import logger


async def handle_webrtc_prepare(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Prepare exact org ICE config before the browser creates a peer."""
    if (event.data or {}).get("protocol_version") != WEBRTC_PROTOCOL_VERSION:
        return _rejected(
            event,
            ctx,
            WsEventAction.WEBRTC_PREPARE,
            "unsupported_protocol_version",
        )
    try:
        data = await S_webrtc_signaling.prepare_session(
            ctx.organization_id,
            ctx.session_id,
        )
        return _response(event, ctx, WsEventAction.WEBRTC_PREPARE, data)
    except NotConfiguredError as error:
        return _response(
            event,
            ctx,
            WsEventAction.WEBRTC_PREPARE,
            {
                "protocol_version": WEBRTC_PROTOCOL_VERSION,
                "command": "prepare",
                "outcome": "rejected",
                "code": "not_configured",
                "capability": error.capability.value,
                "missing": list(error.missing),
                "configure_via": error.configure_via,
            },
            response_status=status.HTTP_409_CONFLICT,
        )
    except WebRTCSignalingError as error:
        return _rejected(event, ctx, WsEventAction.WEBRTC_PREPARE, error.code)
    except Exception as error:
        _log_failure(ctx.organization_id, "prepare", error)
        return _rejected(
            event,
            ctx,
            WsEventAction.WEBRTC_PREPARE,
            "prepare_failed",
        )


async def handle_webrtc_offer(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Acquire and answer one correlated browser offer."""
    try:
        await S_webrtc_signaling.handle_offer(
            ctx.organization_id,
            ctx.session_id,
            event,
        )
        return None
    except WebRTCSignalingError as error:
        return _rejected(event, ctx, WsEventAction.WEBRTC_ANSWER, error.code)
    except Exception as error:
        _log_failure(ctx.organization_id, "offer", error)
        return _rejected(
            event,
            ctx,
            WsEventAction.WEBRTC_ANSWER,
            "offer_failed",
        )


async def handle_webrtc_ice_candidate(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Apply one policy-admitted, correlated remote candidate."""
    try:
        data = await S_webrtc_signaling.handle_candidate(
            ctx.organization_id,
            ctx.session_id,
            event,
        )
        return _response(event, ctx, WsEventAction.WEBRTC_ICE_CANDIDATE, data)
    except WebRTCSignalingError as error:
        return _rejected(
            event,
            ctx,
            WsEventAction.WEBRTC_ICE_CANDIDATE,
            error.code,
        )
    except Exception as error:
        _log_failure(ctx.organization_id, "candidate", error)
        return _rejected(
            event,
            ctx,
            WsEventAction.WEBRTC_ICE_CANDIDATE,
            "candidate_failed",
        )


async def handle_webrtc_hangup(
    event: WsRequestEvent, ctx: SessionContext
) -> Optional[WsResponse]:
    """Run the one idempotent terminal command for a browser hangup."""
    terminated = await terminate_browser_voice(
        ctx,
        reason="client_hangup",
        notify_client=False,
    )
    return _response(
        event,
        ctx,
        WsEventAction.WEBRTC_HANGUP,
        {
            "protocol_version": WEBRTC_PROTOCOL_VERSION,
            "command": "hangup",
            "outcome": "accepted",
            "already_terminated": not terminated,
        },
    )


def _rejected(
    event: WsRequestEvent,
    ctx: SessionContext,
    kind: WsEventAction,
    code: str,
) -> WsResponse:
    command = kind.value.partition(":")[2]
    return _response(
        event,
        ctx,
        kind,
        {
            "protocol_version": WEBRTC_PROTOCOL_VERSION,
            "command": command,
            "outcome": "rejected",
            "code": code,
        },
        response_status=status.HTTP_409_CONFLICT,
    )


def _response(
    event: WsRequestEvent,
    ctx: SessionContext,
    kind: WsEventAction,
    data: dict[str, Any],
    *,
    response_status: int = status.HTTP_200_OK,
) -> WsResponse:
    return WsResponse(
        status=response_status,
        kind=kind,
        organization_id=ctx.organization_id,
        session_id=ctx.session_id,
        request_id=event.request_id,
        data=data,
    )


def _log_failure(organization_id: Any, command: str, error: Exception) -> None:
    logger.warning(
        "WebRTC command failed organization_id=%s command=%s category=%s",
        organization_id,
        command,
        type(error).__name__,
    )
