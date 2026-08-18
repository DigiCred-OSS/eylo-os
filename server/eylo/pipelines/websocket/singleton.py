"""Process-local runtime access for the `websocket` pipeline."""

import logging
from contextlib import asynccontextmanager

from fastapi import WebSocket

from eylo.pipelines.websocket.manager import WsConnectionManager
from eylo.pipelines.websocket.schemas import WSSessionState

logger = logging.getLogger(__name__)
S_ws_manager = WsConnectionManager()


@asynccontextmanager
async def ws_session_context(
    websocket: WebSocket,
    session_state: WSSessionState,
):
    """Enhanced websocket session context manager with better error handling.

    Automatically starts an STT service for each WebSocket connection,
    ensuring that both text and voice modes are supported for every session.

    Args:
        websocket: The WebSocket connection
        organization_id: The organization ID
        session_id: The session ID
        client_info: Optional client information

    """
    connected = False
    _organization_id = session_state.organization_id
    _session_id = session_state.session_id
    _client_info = session_state.client_info
    try:
        # Try to connect to WebSocket
        logger.debug(
            "Establishing WebSocket connection organization_id=%s",
            _organization_id,
        )
        connected = await S_ws_manager.connect(
            websocket, _organization_id, _session_id, _client_info
        )

        if connected:
            # Yield control to the caller
            yield
        else:
            logger.warning(
                "Failed to establish WebSocket connection organization_id=%s",
                _organization_id,
            )
            # No yield here - connection wasn't established
    except Exception as error:
        logger.error(
            "WebSocket session context failed organization_id=%s error_type=%s",
            _organization_id,
            type(error).__name__,
        )
        raise
    finally:
        if connected:
            await S_ws_manager.disconnect(_organization_id, _session_id)


# Start the WebSocket manager's background tasks when the application starts
async def start_websocket_manager():
    """Start the WebSocket manager's background tasks."""
    await S_ws_manager.start_background_tasks()


# Stop the WebSocket manager's background tasks when the application stops
async def stop_websocket_manager():
    """Stop the WebSocket manager's background tasks."""
    await S_ws_manager.stop_background_tasks()


# Export the manager instance and lifecycle functions
__all__ = [
    "start_websocket_manager",
    "stop_websocket_manager",
]
