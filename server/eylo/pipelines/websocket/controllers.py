"""Transport orchestration for the `websocket` pipeline."""

import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

import arrow
from fastapi import Depends, Request, WebSocket, status
from fastapi.websockets import WebSocketState
from starlette.websockets import WebSocketDisconnect

from eylo.common.contracts.websocket import WsResponse
from eylo.common.database import start_transaction
from eylo.modules.auth.services.session_service import (
    AuthSessionService,
    get_auth_session_service,
)
from eylo.modules.user_sessions.domain import (
    UserSessionEntryChannel,
    UserSessionError,
    UserSessionState,
    UserSessionTerminal,
)
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.user_sessions.service import UserSessionService
from eylo.runtime.tasks import (
    monitor_long_running_tasks,
    teardown_long_running_tasks,
    teardown_queues,
)
from eylo.pipelines.websocket.handlers import handle_event
from eylo.pipelines.websocket.schemas import WsEventAction
from eylo.pipelines.websocket.singleton import S_ws_manager

logger = logging.getLogger(__name__)


def extract_client_info(request: Request) -> dict:
    """Extract client information from request headers."""
    try:
        return {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "referer": request.headers.get("referer"),
            "origin": request.headers.get("origin"),
        }
    except Exception:
        return {}


class WebSocketController:
    """Controller for handling WebSocket connections."""

    def __init__(self, auth_session_service: AuthSessionService):
        self._auth_session_service = auth_session_service

    # flake8: noqa
    async def handle_connection(
        self,
        websocket: WebSocket,
        organization_id: UUID,
        session_id: str,
        requested_user_session_id: UUID | None = None,
        request: Optional[Request] = None,
    ):
        """Handles the entire lifecycle of a WebSocket connection."""
        auth_session = await self._auth_session_service.validate_session_token(session_id)

        if not auth_session or auth_session.organization_id != organization_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            logger.warning(
                "WebSocket connection rejected organization_id=%s",
                organization_id,
            )
            return

        try:
            async with start_transaction() as db:
                started = await UserSessionService(db).start_or_resume(
                    organization_id=organization_id,
                    contact_id=auth_session.contact_id,
                    entry_channel=UserSessionEntryChannel.WIDGET,
                    requested_session_id=requested_user_session_id,
                )
                user_session_id = started.user_session.id
                connection_sequence = started.user_session.connection_sequence
        except UserSessionTerminal:
            async with start_transaction() as db:
                started = await UserSessionService(db).start_or_resume(
                    organization_id=organization_id,
                    contact_id=auth_session.contact_id,
                    entry_channel=UserSessionEntryChannel.WIDGET,
                )
                user_session_id = started.user_session.id
                connection_sequence = started.user_session.connection_sequence
        except UserSessionError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            logger.warning(
                "WebSocket user session rejected organization_id=%s",
                organization_id,
            )
            return

        transport_session_id = str(user_session_id)
        await websocket.accept()
        connection_successful = await S_ws_manager.connect(
            websocket,
            organization_id=organization_id,
            session_id=transport_session_id,
            client_info=extract_client_info(request) if request else None,
        )
        if not connection_successful:
            logger.error(
                "Failed to connect WebSocket organization_id=%s",
                organization_id,
            )
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            await self._finish_failed_connection(
                organization_id=organization_id,
                user_session_id=user_session_id,
                connection_sequence=connection_sequence,
                reason="transport.websocket.connection_failed",
            )
            return

        _session_state = S_ws_manager.get_session_state(
            organization_id, transport_session_id
        )
        if not _session_state:
            logger.error(
                "WebSocket session state missing organization_id=%s",
                organization_id,
            )
            await S_ws_manager.disconnect(
                organization_id,
                transport_session_id,
                reason="transport.websocket.session_state_missing",
                expected_websocket=websocket,
            )
            await self._finish_failed_connection(
                organization_id=organization_id,
                user_session_id=user_session_id,
                connection_sequence=connection_sequence,
                reason="transport.websocket.session_state_missing",
            )
            return

        # Associate contact details with the authoritative session state
        _session_state.contact_id = auth_session.contact_id
        _session_state.user_session_id = user_session_id

        await S_ws_manager.associate_contact_session(
            contact_id=auth_session.contact_id,
            session_id=transport_session_id,
            organization_id=organization_id,
        )
        # Build unified SessionContext for this connection
        from eylo.modules.session_context.service import SessionContextHydrator

        ctx = SessionContextHydrator.for_websocket(
            auth_session=auth_session,
            ws_state=_session_state,
        )

        try:
            await self._record_connected(
                organization_id=organization_id,
                user_session_id=user_session_id,
                connection_sequence=connection_sequence,
            )
        except Exception as error:
            logger.error(
                "WebSocket connected fact failed organization_id=%s error_type=%s",
                organization_id,
                type(error).__name__,
            )
        initialized_sent = await S_ws_manager.send_response(
            WsResponse(
                kind=WsEventAction.SESSION_INITIALIZED,
                organization_id=organization_id,
                session_id=transport_session_id,
                data={
                    "user_session_id": str(user_session_id),
                    "connection_sequence": connection_sequence,
                    "created": started.created,
                    "reconnected": started.reconnected,
                },
            ),
            organization_id,
            transport_session_id,
            expected_websocket=websocket,
        )
        if not initialized_sent:
            await S_ws_manager.disconnect(
                organization_id,
                transport_session_id,
                reason="transport.websocket.initialization_failed",
                expected_websocket=websocket,
            )
            await self._finish_failed_connection(
                organization_id=organization_id,
                user_session_id=user_session_id,
                connection_sequence=connection_sequence,
                reason="transport.websocket.initialization_failed",
            )
            return

        _stt_task_definitions = {}
        _tts_task_definitions = {}
        _stt_active_tasks = {}
        _tts_active_tasks = {}
        _stt_task_params = {}
        _tts_task_params = {}

        close_reason = "transport.websocket.disconnected"
        explicitly_ended = False
        cancellation: asyncio.CancelledError | None = None
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect(
                        code=int(
                            message.get("code") or status.WS_1000_NORMAL_CLOSURE
                        ),
                        reason=message.get("reason"),
                    )
                response_payload = None
                request_payload = None

                try:
                    if "text" in message and message["text"] is not None:
                        # Handle text messages
                        request_payload = json.loads(message["text"])
                        request_payload = await S_ws_manager.validate_incoming_message(
                            request_payload, _session_state
                        )
                        if request_payload:
                            response_payload = await handle_event(
                                request_payload=request_payload,
                                ctx=ctx,
                            )
                    elif "bytes" in message and message["bytes"] is not None:
                        # Handle binary messages
                        request_payload = {
                            "kind": WsEventAction.AUDIO_DATA,
                            "data": {
                                "audio_data": message["bytes"],
                                "timestamp": arrow.utcnow().timestamp(),
                            },
                        }
                        response_payload = await handle_event(
                            request_payload=request_payload,
                            ctx=ctx,
                        )
                    else:
                        # Handle invalid message format
                        logger.warning(
                            "Invalid WebSocket frame organization_id=%s has_text=%s "
                            "has_bytes=%s",
                            organization_id,
                            message.get("text") is not None,
                            message.get("bytes") is not None,
                        )
                        response_payload = {
                            "kind": WsEventAction.ERROR,
                            "data": {
                                "error": status.HTTP_400_BAD_REQUEST,
                                "message": "Invalid message format",
                            },
                        }
                except json.JSONDecodeError:
                    text_length = len(message.get("text") or "")
                    logger.warning(
                        "Invalid WebSocket JSON organization_id=%s text_length=%s",
                        organization_id,
                        text_length,
                    )
                    response_payload = {
                        "kind": WsEventAction.ERROR,
                        "data": {
                            "error": status.HTTP_400_BAD_REQUEST,
                            "message": "Invalid JSON format",
                        },
                    }
                except Exception as error:
                    logger.error(
                        "WebSocket message processing failed "
                        "organization_id=%s error_type=%s",
                        organization_id,
                        type(error).__name__,
                    )
                    response_payload = {
                        "kind": WsEventAction.ERROR,
                        "data": {
                            "error": status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "message": "Error processing request",
                        },
                    }

                if response_payload:
                    await S_ws_manager.send_response(
                        response_payload,
                        organization_id,
                        transport_session_id,
                        expected_websocket=websocket,
                    )

                await monitor_long_running_tasks(
                    task_definitions={**_stt_task_definitions, **_tts_task_definitions},
                    active_tasks={**_stt_active_tasks, **_tts_active_tasks},
                    task_params={**_stt_task_params, **_tts_task_params},
                    exceptions_to_ignore={asyncio.CancelledError},
                )
        except WebSocketDisconnect as error:
            explicitly_ended = (
                error.code == status.WS_1000_NORMAL_CLOSURE
                and error.reason == "user_session_end"
            )
            close_reason = (
                "widget.closed"
                if explicitly_ended
                else "transport.websocket.disconnected"
            )
            await S_ws_manager.disconnect(
                organization_id,
                transport_session_id,
                reason=close_reason,
                expected_websocket=websocket,
            )
            logger.info(
                "WebSocket disconnected normally organization_id=%s",
                organization_id,
            )
        except Exception as error:
            close_reason = "transport.websocket.failed"
            logger.error(
                "WebSocket error organization_id=%s category=%s",
                organization_id,
                type(error).__name__,
            )
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "kind": WsEventAction.ERROR,
                                "data": {
                                    "error": status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    "message": "An unexpected error occurred",
                                },
                            }
                        )
                    )
            except Exception:
                pass

            await S_ws_manager.disconnect(
                organization_id,
                transport_session_id,
                reason=close_reason,
                expected_websocket=websocket,
            )
        except asyncio.CancelledError as error:
            cancellation = error
            close_reason = "transport.websocket.cancelled"
            await S_ws_manager.disconnect(
                organization_id,
                transport_session_id,
                reason=close_reason,
                expected_websocket=websocket,
            )

        # One terminal command owns signaling, audio, and durable session truth.
        from eylo.pipelines.voice.browser import terminate_browser_voice

        try:
            await terminate_browser_voice(
                ctx,
                reason="websocket_disconnected",
                notify_client=False,
            )
        except Exception as error:
            logger.error(
                "Browser voice cleanup failed organization_id=%s error_type=%s",
                organization_id,
                type(error).__name__,
            )
        try:
            await self._record_disconnected(
                organization_id=organization_id,
                user_session_id=user_session_id,
                connection_sequence=connection_sequence,
                explicitly_ended=explicitly_ended,
                reason=close_reason,
            )
        except Exception as error:
            logger.error(
                "WebSocket session close persistence failed organization_id=%s "
                "error_type=%s",
                organization_id,
                type(error).__name__,
            )
        if cancellation is not None:
            raise cancellation

    @staticmethod
    async def _record_connected(
        *,
        organization_id: UUID,
        user_session_id: UUID,
        connection_sequence: int,
    ) -> None:
        async with start_transaction() as db:
            await file_user_session_fact(
                db,
                organization_id=organization_id,
                user_session_id=user_session_id,
                subject_type="transport.websocket",
                subject_id=user_session_id,
                event_type="transport.websocket.connected",
                payload={"connection_sequence": connection_sequence},
            )

    @staticmethod
    async def _record_disconnected(
        *,
        organization_id: UUID,
        user_session_id: UUID,
        connection_sequence: int,
        explicitly_ended: bool,
        reason: str,
    ) -> None:
        async with start_transaction() as db:
            service = UserSessionService(db)
            if explicitly_ended:
                await service.finish(
                    organization_id=organization_id,
                    user_session_id=user_session_id,
                    state=UserSessionState.ENDED,
                    reason=reason,
                    expected_connection_sequence=connection_sequence,
                )
            else:
                await service.disconnect(
                    organization_id=organization_id,
                    user_session_id=user_session_id,
                    reason=reason,
                    expected_connection_sequence=connection_sequence,
                )
            await file_user_session_fact(
                db,
                organization_id=organization_id,
                user_session_id=user_session_id,
                subject_type="transport.websocket",
                subject_id=user_session_id,
                event_type=(
                    "transport.websocket.failed"
                    if reason == "transport.websocket.failed"
                    else "transport.websocket.disconnected"
                ),
                payload={
                    "reason": reason,
                    "connection_sequence": connection_sequence,
                },
            )

    @staticmethod
    async def _finish_failed_connection(
        *,
        organization_id: UUID,
        user_session_id: UUID,
        connection_sequence: int,
        reason: str,
    ) -> None:
        async with start_transaction() as db:
            await UserSessionService(db).finish(
                organization_id=organization_id,
                user_session_id=user_session_id,
                state=UserSessionState.FAILED,
                reason=reason,
                expected_connection_sequence=connection_sequence,
            )
            await file_user_session_fact(
                db,
                organization_id=organization_id,
                user_session_id=user_session_id,
                subject_type="transport.websocket",
                subject_id=user_session_id,
                event_type="transport.websocket.failed",
                payload={
                    "reason": reason,
                    "connection_sequence": connection_sequence,
                },
            )


def get_websocket_controller(
    auth_session_service: AuthSessionService = Depends(get_auth_session_service),
) -> WebSocketController:
    """Dependency provider for the WebSocketController."""
    return WebSocketController(auth_session_service=auth_session_service)
