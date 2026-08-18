"""Organization-scoped WebSocket connection ownership and event delivery."""

import asyncio
import base64
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

import arrow
from fastapi import APIRouter, WebSocket, status
from fastapi.websockets import WebSocketState
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect
from uuid_utils import uuid7

from eylo.common.database import json_serializer, start_transaction
from eylo.common.redis import get_redis_client
from eylo.modules.agents.models import AgentStatus
from eylo.modules.agents.schemas.api import AgentWsResponseSchema
from eylo.modules.agents.services.revisions import AgentRevisionService
from eylo.pipelines.voice.session_tts import enqueue_conversation_tts_payload
from eylo.pipelines.websocket.schemas import (
    ContactUUID,
    ConversationUUID,
    OrganizationUUID,
    WSSessionState,
    WSSessionType,
    WsEventAction,
    WsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])

EYLO_WS_KEY_PREFIX = "eylo::ws"
EYLO_WEBRTC_PUBSUB_CHANNEL = f"{EYLO_WS_KEY_PREFIX}::webrtc::pubsub"
_CONVERSATION_SCOPED_PUBSUB_EVENTS = frozenset(
    {
        WsEventAction.CONVERSATION_CREATED,
        WsEventAction.CONVERSATION_READ,
        WsEventAction.CONVERSATION_UPDATED,
        WsEventAction.MESSAGE_CREATED,
        WsEventAction.MESSAGE_STATUS,
        WsEventAction.MESSAGE_TRANSCRIPT,
        WsEventAction.PARTICIPANT_CREATED,
        WsEventAction.PARTICIPANT_UPDATED,
        WsEventAction.AGENT_THINKING,
        WsEventAction.AGENT_PROCESSING,
        WsEventAction.TOOL_EXECUTING,
        WsEventAction.TOOL_COMPLETED,
        WsEventAction.AGENT_RESPONSE_COMPLETE,
    }
)

class WSPubSubManager:
    def __init__(self, default_channel: str):
        self._redis = get_redis_client()
        self._pubsub = self._redis.pubsub()
        self.default_channel = default_channel

    async def subscribe(self, channel: str | None = None):
        """Subscribe to a Redis channel."""
        await self._pubsub.subscribe(channel or self.default_channel)

    async def unsubscribe(self, channel: str | None = None):
        """Unsubscribe from a Redis channel."""
        await self._pubsub.unsubscribe(channel or self.default_channel)

    async def publish(
        self, message: Union[dict, BaseModel], channel: str | None = None
    ):
        """Publish a message to a Redis channel."""
        if isinstance(message, BaseModel):
            message = message.model_dump_json(by_alias=True)
        elif isinstance(message, dict):
            message = json_serializer(message)
        await self._redis.publish(channel or self.default_channel, message)

    async def listen(self):
        """Listen for messages on subscribed channels."""
        while True:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                yield message
            await asyncio.sleep(0.1)


class WsConnectionManager:
    """Enhanced WebSocket connection manager with improved scalability and reliability.

    This class handles the lifecycle of WebSocket connections, associating them
    with unique organization and session identifiers. It maintains an in-memory
    registry of active connections for quick access and utilizes Redis for
    persistent storage of session metadata and associations.

    Key features:
    - Connection health monitoring
    - Distributed operation across multiple instances
    - Improved error handling and recovery
    - Connection statistics and monitoring
    - Rate limiting and overload protection
    """

    # Connection settings
    CONNECTION_TIMEOUT = 30.0  # seconds
    MAX_MESSAGE_SIZE = 1024 * 1024 * 5  # 5MB
    MAX_CONNECTIONS_PER_ORG = 10000  # Prevent DOS
    MAX_CONNECTIONS_TOTAL = 50000  # Overall limit
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_MESSAGES = 300  # messages per window

    @property
    def id(self):
        """Unique identifier for this connection manager instance."""
        return self._id

    def __init__(self):
        self._id = uuid7()
        # Additional tracking for enhanced functionality
        self._rate_limits: Dict[Tuple[OrganizationUUID, str], List[float]] = (
            defaultdict(list)
        )

        self._active_connections: Dict[Tuple[OrganizationUUID, str], WebSocket] = {}
        self._session_contact: Dict[Tuple[OrganizationUUID, str], ContactUUID] = {}
        self._contact_sessions: Dict[Tuple[OrganizationUUID, ContactUUID], Set[str]] = (
            defaultdict(set)
        )
        self._conversation_sessions: Dict[
            Tuple[OrganizationUUID, ConversationUUID], Set[str]
        ] = defaultdict(set)
        self._session_conversations: Dict[
            Tuple[OrganizationUUID, str], ConversationUUID
        ] = {}

        self._redis = get_redis_client()
        self._pubsub_manager = WSPubSubManager(
            default_channel=f"{EYLO_WS_KEY_PREFIX}::pubsub"
        )
        self._webrtc_pubsub_manager = WSPubSubManager(
            default_channel=EYLO_WEBRTC_PUBSUB_CHANNEL
        )
        self._tasks = []
        self.sessions: Dict[Tuple[OrganizationUUID, str], WSSessionState] = {}

        logger.info(f"Initialized WebSocket manager {self.id}")

    def __repr__(self):
        return f"<WsConnectionManager id={self.id}>"

    def _get_session_key(
        self, organization_id: OrganizationUUID, session_id: str
    ) -> Tuple[OrganizationUUID, str]:
        """Get the key tuple for a session based on organization and session IDs."""
        return (organization_id, session_id)

    def _get_contact_key(
        self, organization_id: OrganizationUUID, contact_id: ContactUUID
    ) -> Tuple[OrganizationUUID, ContactUUID]:
        """Get the key tuple for a contact based on organization and contact IDs."""
        return (organization_id, contact_id)

    # Rate limiting
    async def _check_rate_limit(self, org_id: UUID, session_id: str) -> bool:
        """Check if a connection has exceeded its rate limit.

        Returns:
            True if within rate limit, False if exceeded

        """
        key = (org_id, session_id)
        now = arrow.utcnow().timestamp()

        # Add the current timestamp
        self._rate_limits[key].append(now)

        # Remove timestamps outside the window
        window_start = now - self.RATE_LIMIT_WINDOW
        self._rate_limits[key] = [
            ts for ts in self._rate_limits[key] if ts > window_start
        ]

        # Check if we've exceeded the limit
        return len(self._rate_limits[key]) <= self.RATE_LIMIT_MAX_MESSAGES

    async def _get_active_connection(self, organization_id: UUID, session_id: str):
        """Get active WebSocket for a session if it exists."""
        return self._active_connections.get(
            self._get_session_key(organization_id, session_id)
        )

    async def _set_active_connection(
        self, organization_id: UUID, session_id: str, websocket: WebSocket
    ):
        """Register an active WebSocket session."""
        self._active_connections[self._get_session_key(organization_id, session_id)] = (
            websocket
        )

    async def _check_active_connection_status(
        self, organization_id: UUID, session_id: str
    ):
        """Get active WebSocket for a session if it exists."""
        ws = self._active_connections.get(
            self._get_session_key(organization_id, session_id)
        )
        return ws and ws.client_state == WebSocketState.CONNECTED

    async def _remove_from_active_connection(
        self,
        organization_id: OrganizationUUID,
        session_id: str,
        *,
        expected_websocket: WebSocket | None = None,
    ) -> bool:
        """Remove only the transport generation owned by the caller."""
        key = self._get_session_key(organization_id, session_id)
        active_websocket = self._active_connections.get(key)
        if (
            expected_websocket is not None
            and active_websocket is not None
            and active_websocket is not expected_websocket
        ):
            return False
        self._active_connections.pop(key, None)
        self._rate_limits.pop(key, None)
        self.sessions.pop(key, None)
        contact_id_for_session = self._session_contact.pop(key, None)
        if contact_id_for_session:
            contact_key = self._get_contact_key(organization_id, contact_id_for_session)
            contact_sessions = self._contact_sessions.get(contact_key)
            if contact_sessions is not None:
                contact_sessions.discard(session_id)
                if not contact_sessions:
                    self._contact_sessions.pop(contact_key, None)
        conversation_id_for_session = self._session_conversations.pop(key, None)
        if conversation_id_for_session:
            conversation_key = (organization_id, conversation_id_for_session)
            conversation_sessions = self._conversation_sessions.get(conversation_key)
            if conversation_sessions is not None:
                conversation_sessions.discard(session_id)
                if not conversation_sessions:
                    self._conversation_sessions.pop(conversation_key, None)
        return active_websocket is not None

    async def _init_connection(
        self,
        organization_id: UUID,
        session_id: str,
        websocket: WebSocket,
        client_info: dict | None = None,
    ):
        """Initialize a session in Redis and memory.

        Returns:
            True if successful, False if rejected due to limits

        """
        key = self._get_session_key(organization_id, session_id)
        replacing_connection = key in self._active_connections

        # Replacing one transport generation does not consume another slot.
        org_connections = sum(
            1 for (org, _) in self._active_connections.keys() if org == organization_id
        )

        if not replacing_connection and org_connections >= self.MAX_CONNECTIONS_PER_ORG:
            logger.warning(
                f"Connection limit reached for organization {organization_id}"
            )
            return False

        # Check total connection limit
        if (
            not replacing_connection
            and len(self._active_connections) >= self.MAX_CONNECTIONS_TOTAL
        ):
            logger.warning("Total connection limit reached")
            return False

        await self._set_active_connection(organization_id, session_id, websocket)
        return True

    async def _destroy_connection(
        self,
        organization_id: UUID,
        session_id: str,
        *,
        expected_websocket: WebSocket | None = None,
    ) -> bool:
        """Remove a transport without allowing stale cleanup to remove its successor."""
        return await self._remove_from_active_connection(
            organization_id,
            session_id,
            expected_websocket=expected_websocket,
        )

    @staticmethod
    async def _close_replaced_connection(websocket: WebSocket | None) -> None:
        if websocket is None:
            return
        try:
            await websocket.close(code=1000, reason="transport_replaced")
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception as error:
            logger.debug(
                "Replaced WebSocket close failed error_type=%s",
                type(error).__name__,
            )

    async def _get_available_agents(
        self,
        organization_id: OrganizationUUID,
    ) -> List[dict]:
        async with start_transaction(ro=True):
            revisions = await AgentRevisionService().list_available_for_widget(
                organization_id=organization_id,
            )
            return [
                AgentWsResponseSchema.model_validate(
                    {
                        "id": revision.agent_id,
                        "name": revision.name,
                        "slug": revision.slug,
                        "status": AgentStatus.ACTIVE,
                        "organization_id": revision.organization_id,
                        "description": revision.description,
                        "deleted": False,
                        "created_at": revision.created_at,
                        "updated_at": revision.updated_at,
                    }
                ).model_dump(by_alias=True)
                for revision in revisions
            ]

    # Tasks
    async def _listen_for_pubsub_messages(self):
        while True:
            try:
                async for message in self._pubsub_manager.listen():
                    if message and message["type"] == "message":
                        logger.debug("WebSocket pubsub message received")

                        try:
                            data = message["data"].decode("utf-8")
                            data = json.loads(data)

                            contact_id = UUID(data["contact_id"])
                            organization_id = UUID(data["organization_id"])
                            payload = data["payload"]
                            kind = WsEventAction(data["kind"])
                            conversation_id = _pubsub_conversation_id(
                                data,
                                kind=kind,
                            )
                            await self._send_response_to_contact(
                                contact_id=contact_id,
                                organization_id=organization_id,
                                conversation_id=conversation_id,
                                payload=payload,
                                kind=kind,
                            )

                        except (
                            json.JSONDecodeError,
                            KeyError,
                            TypeError,
                            ValueError,
                        ) as error:
                            logger.error(
                                "WebSocket pubsub message rejected error_type=%s",
                                type(error).__name__,
                            )
            except Exception as error:
                logger.error(
                    "WebSocket pubsub listener failed error_type=%s",
                    type(error).__name__,
                )
                await asyncio.sleep(1)

    async def _listen_for_webrtc_pubsub_messages(self):
        while True:
            try:
                async for message in self._webrtc_pubsub_manager.listen():
                    if message and message["type"] == "message":
                        try:
                            data = message["data"].decode("utf-8")
                            data = json.loads(data)
                            await enqueue_conversation_tts_payload(
                                router=self,
                                conversation_id=data["conversation_id"],
                                organization_id=data["organization_id"],
                                payload=data["payload"],
                            )
                        except json.JSONDecodeError as error:
                            logger.error(
                                "WebRTC pubsub decode failed error_type=%s",
                                type(error).__name__,
                            )
            except Exception as error:
                logger.error(
                    "WebRTC pubsub listener failed error_type=%s",
                    type(error).__name__,
                )
                await asyncio.sleep(1)

    async def start_background_tasks(self):
        await self._pubsub_manager.subscribe()
        await self._webrtc_pubsub_manager.subscribe()
        self._tasks.append(asyncio.create_task(self._listen_for_pubsub_messages()))
        self._tasks.append(
            asyncio.create_task(self._listen_for_webrtc_pubsub_messages())
        )

    async def stop_background_tasks(self):
        await self._pubsub_manager.unsubscribe()
        await self._webrtc_pubsub_manager.unsubscribe()
        for task in self._tasks:
            try:
                task.cancel()
            except Exception as cancellation_error:
                # `except Exception`, not a bare `except`: cancellation is a
                # BaseException, and swallowing it here would suppress the very
                # shutdown this loop is performing.
                logger.debug(
                    "Task cancel raised during shutdown error_type=%s",
                    type(cancellation_error).__name__,
                )
        self._tasks.clear()

    # PUBLIC API
    async def connect(
        self,
        websocket: WebSocket,
        organization_id: UUID,
        session_id: str,
        client_info: dict | None = None,
    ) -> bool:
        """Connect a new WebSocket client with reliability enhancements."""
        session_key = self._get_session_key(organization_id, session_id)
        session_state = WSSessionState(
            organization_id=organization_id,
            session_id=session_id,
            client_info=client_info,
        )
        logger.info(
            "WebSocket session state created organization_id=%s state_id=%s",
            organization_id,
            id(session_state),
        )
        try:
            available_agents = await self._get_available_agents(organization_id)
            previous_websocket = await self._get_active_connection(
                organization_id, session_id
            )
            is_under_rate_limits = await self._init_connection(
                organization_id, session_id, websocket, client_info
            )
            if not is_under_rate_limits:
                await websocket.close(code=1013, reason="Connection limit reached")
                return False
            self.sessions[session_key] = session_state
            if previous_websocket is not websocket:
                await self._close_replaced_connection(previous_websocket)

            # Send welcome message with connection info
            welcome_payload = WsResponse.model_validate(
                {
                    "kind": WsEventAction.SYSTEM_MESSAGE,
                    "data": {
                        "message": "Connection established",
                        "level": "info",
                        "timestamp": arrow.utcnow().timestamp(),
                        "limits": {
                            "maxMessageSize": self.MAX_MESSAGE_SIZE,
                            "rateLimitMessages": self.RATE_LIMIT_MAX_MESSAGES,
                            "rateLimitWindow": self.RATE_LIMIT_WINDOW,
                        },
                        "agents": available_agents,
                    },
                    "organization_id": organization_id,
                    "session_id": session_id,
                }
            )
            welcome_sent = await self.send_response(
                payload=welcome_payload,
                organization_id=organization_id,
                session_id=session_id,
                expected_websocket=websocket,
            )
            return bool(welcome_sent)
        except Exception as error:
            logger.error(
                "Failed to establish WebSocket connection "
                "organization_id=%s error_type=%s",
                organization_id,
                type(error).__name__,
            )
            await self._destroy_connection(
                organization_id,
                session_id,
                expected_websocket=websocket,
            )
            return False

    def get_session_state(
        self, organization_id: UUID, session_id: str
    ) -> WSSessionState | None:
        """Retrieves the session state for a given session."""
        session_key = self._get_session_key(organization_id, session_id)
        session_state = self.sessions.get(session_key)
        return session_state

    async def register_telephony_session(
        self,
        websocket: WebSocket,
        organization_id: UUID,
        session_id: str,
        contact_id: UUID,
        user_session_id: UUID,
        stream_sid: str,
        provider: str,
    ) -> bool:
        """Register a new telephony media stream session for any provider."""
        _PROVIDER_SESSION_TYPES = {
            "twilio": WSSessionType.TWILIO,
            "plivo": WSSessionType.PLIVO,
            "vonage": WSSessionType.VONAGE,
            "exotel": WSSessionType.EXOTEL,
        }
        try:
            session_type = _PROVIDER_SESSION_TYPES[provider]
        except KeyError:
            raise ValueError(f"Unsupported telephony provider: {provider}") from None

        session_key = self._get_session_key(organization_id, session_id)
        session_state = WSSessionState(
            organization_id=organization_id,
            session_id=session_id,
            session_type=session_type,
            stream_sid=stream_sid,
            contact_id=contact_id,
            user_session_id=user_session_id,
        )
        previous_websocket = await self._get_active_connection(
            organization_id, session_id
        )
        is_under_rate_limits = await self._init_connection(
            organization_id, session_id, websocket
        )
        if not is_under_rate_limits:
            await websocket.close(code=1013, reason="Connection limit reached")
            return False
        self.sessions[session_key] = session_state
        if previous_websocket is not websocket:
            await self._close_replaced_connection(previous_websocket)

        await self.associate_contact_session(
            contact_id=contact_id,
            session_id=session_id,
            organization_id=organization_id,
        )
        return True

    async def disconnect(
        self,
        organization_id: UUID,
        session_id: str,
        reason: str = "client_disconnect",
        *,
        expected_websocket: WebSocket | None = None,
    ) -> bool:
        """Disconnect a WebSocket client with graceful cleanup.

        Returns:
            True if disconnection successful, False if client already disconnected

        """
        websocket = await self._get_active_connection(organization_id, session_id)
        if expected_websocket is not None and websocket is not expected_websocket:
            return False
        if websocket:
            try:
                # Send goodbye message
                try:
                    goodbye_payload = {
                        "kind": WsEventAction.SYSTEM_MESSAGE,
                        "data": {
                            "message": "Connection closing",
                            "level": "info",
                            "reason": reason,
                            "timestamp": arrow.utcnow().timestamp(),
                        },
                    }
                    await websocket.send_text(json.dumps(goodbye_payload))
                except Exception as goodbye_error:
                    # Best effort — the peer may already be gone. Narrowed from
                    # a bare `except` because this awaits: a CancelledError
                    # arriving mid-send was swallowed, and the coroutine carried
                    # on after having been cancelled.
                    logger.debug(
                        "Goodbye frame not delivered error_type=%s",
                        type(goodbye_error).__name__,
                    )

                # Close the socket
                await websocket.close(code=1000, reason=reason)
            except (WebSocketDisconnect, RuntimeError):
                pass
            except Exception as error:
                logger.error(
                    "WebSocket disconnect failed organization_id=%s error_type=%s",
                    organization_id,
                    type(error).__name__,
                )

            # Always clean up the session
            await self._destroy_connection(
                organization_id,
                session_id,
                expected_websocket=websocket,
            )
            return True
        return False

    async def send_response(
        self,
        payload: Union[str, dict, BaseModel, bytes],
        organization_id: UUID,
        session_id: str,
        *,
        expected_websocket: WebSocket | None = None,
    ) -> bool:
        """Send a message to a WebSocket client with metrics tracking.

        Args:
            payload: The message payload to send
            organization_id: Organization ID
            session_id: Session ID
            priority: Message priority (0-9, higher is more important)

        Returns:
            True if message sent successfully, False otherwise

        """
        key = self._get_session_key(organization_id, session_id)
        websocket = self._active_connections.get(key)
        session_state = self.sessions.get(key)

        if expected_websocket is not None and websocket is not expected_websocket:
            return False

        if not websocket or not session_state:
            logger.warning(
                "Attempted to send to inactive WebSocket organization_id=%s",
                organization_id,
            )
            await self._destroy_connection(
                organization_id,
                session_id,
                expected_websocket=expected_websocket,
            )
            return False

        try:
            # Prepare the payload
            if isinstance(payload, bytes):
                if session_state.session_type == WSSessionType.TWILIO:
                    # Twilio: base64 audio wrapped in JSON
                    payload_b64 = base64.b64encode(payload).decode("ascii")
                    twilio_msg = {
                        "event": "media",
                        "streamSid": session_state.stream_sid,
                        "media": {"payload": payload_b64},
                    }
                    await websocket.send_text(json.dumps(twilio_msg))
                elif session_state.session_type == WSSessionType.PLIVO:
                    # Plivo: base64 audio in JSON (playAudio event)
                    payload_b64 = base64.b64encode(payload).decode("ascii")
                    plivo_msg = {
                        "event": "playAudio",
                        "media": {
                            "payload": payload_b64,
                            "sampleRate": "8000",
                            "contentType": "audio/x-mulaw",
                        },
                    }
                    await websocket.send_text(json.dumps(plivo_msg))
                elif session_state.session_type == WSSessionType.VONAGE:
                    # Vonage: raw binary LINEAR16 frames
                    await websocket.send_bytes(payload)
                elif session_state.session_type == WSSessionType.EXOTEL:
                    # Exotel: raw binary LINEAR16 frames
                    await websocket.send_bytes(payload)
                else:
                    # Browser / default
                    await websocket.send_bytes(payload)
            else:
                # Prepare text data
                text_payload = ""  # Initialize to prevent unbound error

                # Use a custom serializer to handle non-standard types like bytes, enums, etc.
                def custom_serializer(obj):
                    if isinstance(obj, bytes):
                        return obj.decode("utf-8", "ignore")
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    if hasattr(obj, "value"):  # Handle Enums
                        return obj.value
                    if isinstance(obj, UUID):
                        return str(obj)
                    raise TypeError(
                        f"Object of type {type(obj).__name__} is not JSON serializable"
                    )

                if isinstance(payload, BaseModel):
                    # Dump the model to a dict first, then serialize with custom logic
                    data_to_serialize = payload.model_dump(
                        mode="python",
                        by_alias=True,
                    )
                elif isinstance(payload, dict):
                    data_to_serialize = payload
                else:
                    text_payload = str(payload)
                    data_to_serialize = None

                if data_to_serialize:
                    text_payload = json.dumps(
                        data_to_serialize, default=custom_serializer
                    )

                # Send the text
                await websocket.send_text(text_payload)
            return True
        except WebSocketDisconnect:
            logger.info(
                "WebSocket disconnected while sending organization_id=%s",
                organization_id,
            )
            await self._destroy_connection(
                organization_id,
                session_id,
                expected_websocket=websocket,
            )
        except RuntimeError:
            logger.info(
                "WebSocket send rejected by runtime organization_id=%s",
                organization_id,
            )
            await self._destroy_connection(
                organization_id,
                session_id,
                expected_websocket=websocket,
            )
        except Exception as e:
            kind = None
            if isinstance(payload, BaseModel):
                kind = getattr(payload, "kind", None)
            elif isinstance(payload, dict):
                kind = payload.get("kind")
            logger.error(
                "Failed to send response org=%s kind=%s category=%s",
                organization_id,
                kind,
                type(e).__name__,
            )
            # Try to disconnect on error
            try:
                await self.disconnect(
                    organization_id,
                    session_id,
                    "send_error",
                    expected_websocket=websocket,
                )
            except Exception as disconnect_error:
                # Same narrowing, same reason: this awaits, so a bare `except`
                # swallowed cancellation. The `finally` below still runs.
                logger.debug(
                    "Disconnect after send failure raised error_type=%s",
                    type(disconnect_error).__name__,
                )
            finally:
                await self._destroy_connection(
                    organization_id,
                    session_id,
                    expected_websocket=websocket,
                )
            return False

    async def broadcast(
        self,
        payload: Union[str, dict, BaseModel, bytes],
        organization_id: UUID,
        session_ids: List[str] | None = None,
        exclude_session_id: str | None = None,
    ):
        """Broadcast a message to multiple sessions efficiently.

        Returns:
            Number of successful sends

        """
        if session_ids is None:
            # Broadcast to all sessions in organization
            targets = [
                sid
                for (oid, sid) in self._active_connections.keys()
                if oid == organization_id and sid != exclude_session_id
            ]
        else:
            # Broadcast only to specified sessions
            targets = [
                sid
                for sid in session_ids
                if (organization_id, sid) in self._active_connections
                and sid != exclude_session_id
            ]

        for session_id in targets:
            try:
                await self.send_response(payload, organization_id, session_id)

            except Exception as error:
                logger.warning(
                    "WebSocket broadcast failed organization_id=%s error_type=%s",
                    organization_id,
                    type(error).__name__,
                )

    async def associate_contact_session(
        self, contact_id: UUID, session_id: str, organization_id: UUID
    ):
        """Associate a contact with a session."""
        self._session_contact[self._get_session_key(organization_id, session_id)] = (
            contact_id
        )
        contact_key = self._get_contact_key(organization_id, contact_id)
        self._contact_sessions[contact_key].add(session_id)

    async def associate_conversation_session(
        self,
        conversation_id: UUID,
        session_id: str,
        organization_id: UUID,
    ):
        """Associate a conversation with a session."""
        conversation_key = (organization_id, conversation_id)
        session_key = self._get_session_key(organization_id, session_id)

        self._conversation_sessions[conversation_key].add(session_id)
        self._session_conversations[session_key] = conversation_id

    async def get_sessions_for_conversation(
        self,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> Set[str]:
        """Get all active sessions for a conversation."""
        key = (organization_id, conversation_id)
        return self._conversation_sessions.get(key, set())

    async def get_latest_session_for_conversation(
        self,
        organization_id: UUID,
        conversation_id: UUID,
    ) -> WSSessionState | None:
        """Get the most recently active session state for a conversation."""
        session_ids = await self.get_sessions_for_conversation(
            organization_id, conversation_id
        )

        latest_session_state: WSSessionState | None = None
        latest_activity: float = 0

        for session_id in session_ids:
            session_state = self.get_session_state(organization_id, str(session_id))
            if (
                session_state
                and session_state.last_activity_at
                and session_state.last_activity_at > latest_activity
            ):
                latest_activity = session_state.last_activity_at
                latest_session_state = session_state

        return latest_session_state

    async def get_sessions_for_contact(
        self,
        organization_id: UUID,
        contact_id: UUID,
    ) -> Set[str]:
        """Get the active session for a contact."""
        contact_key = self._get_contact_key(organization_id, contact_id)
        return self._contact_sessions.get(contact_key, set())

    async def get_contact_for_session(
        self, organization_id: UUID, session_id: str
    ) -> Optional[UUID]:
        """Get the contact associated with a session."""
        session_key = self._get_session_key(organization_id, session_id)
        return self._session_contact.get(session_key)

    async def validate_incoming_message(
        self,
        message: Union[dict, bytes],
        session_state: WSSessionState,
    ):
        # Update activity timestamp
        organization_id = session_state.organization_id
        session_id = session_state.session_id
        now = arrow.utcnow().timestamp()
        session_state.last_activity_at = now
        # For binary messages, return directly
        if isinstance(message, bytes):
            return message

        # Check rate limits for text messages
        if not await self._check_rate_limit(organization_id, session_id):
            logger.warning(
                "WebSocket rate limit exceeded organization_id=%s",
                organization_id,
            )
            await self.send_response(
                {
                    "kind": WsEventAction.ERROR,
                    "data": {
                        "error": status.HTTP_429_TOO_MANY_REQUESTS,
                        "message": "Rate limit exceeded. Please slow down.",
                        "timestamp": now,
                    },
                },
                organization_id,
                session_id,
            )
            return None

        return message

    async def reply_to_contact(
        self,
        contact_id: ContactUUID | str,
        organization_id: OrganizationUUID,
        payload: dict,
        kind: WsEventAction,
    ):
        if kind in _CONVERSATION_SCOPED_PUBSUB_EVENTS:
            raise ValueError(
                f"{kind.value} requires conversation-scoped WebSocket routing."
            )
        await self._publish_to_contact(
            contact_id=contact_id,
            organization_id=organization_id,
            conversation_id=None,
            payload=payload,
            kind=kind,
        )

    async def reply_to_conversation_contact(
        self,
        *,
        contact_id: ContactUUID | str,
        organization_id: OrganizationUUID,
        conversation_id: ConversationUUID,
        payload: dict,
        kind: WsEventAction,
    ) -> None:
        """Publish a conversation delta only to sessions bound to that chat."""
        await self._publish_to_contact(
            contact_id=contact_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            payload=payload,
            kind=kind,
        )

    async def _publish_to_contact(
        self,
        *,
        contact_id: ContactUUID | str,
        organization_id: OrganizationUUID,
        conversation_id: ConversationUUID | None,
        payload: dict,
        kind: WsEventAction,
    ) -> None:
        message = {
            "contact_id": str(contact_id),
            "organization_id": str(organization_id),
            "payload": payload,
            "kind": kind.value,
        }
        if conversation_id is not None:
            message["conversation_id"] = str(conversation_id)
        await self._pubsub_manager.publish(message=message)

    async def _send_response_to_contact(
        self,
        contact_id: ContactUUID | str,
        organization_id: OrganizationUUID | str,
        conversation_id: ConversationUUID | None,
        payload: dict,
        kind: WsEventAction,
    ):
        contact_id = UUID(str(contact_id))
        organization_id = UUID(str(organization_id))
        contact_sessions = await self.get_sessions_for_contact(
            organization_id,
            contact_id,
        )
        session_ids = set(contact_sessions)
        if conversation_id is not None:
            conversation_id = UUID(str(conversation_id))
            conversation_sessions = await self.get_sessions_for_conversation(
                organization_id,
                conversation_id,
            )
            session_ids = {
                session_id
                for session_id in contact_sessions
                if (
                    (state := self.get_session_state(organization_id, session_id))
                    is not None
                    and (
                        state.session_type == WSSessionType.BROWSER
                        or session_id in conversation_sessions
                    )
                )
            }

        logger.info(
            "Replying to contact sessions organization_id=%s "
            "conversation_id=%s session_count=%s",
            organization_id,
            conversation_id,
            len(session_ids),
        )

        for session_id in session_ids:
            await self.send_response(
                payload=WsResponse(
                    status=status.HTTP_200_OK,
                    kind=kind,
                    data=payload,
                    organization_id=organization_id,
                    session_id=session_id,
                ),
                organization_id=organization_id,
                session_id=session_id,
            )

    async def conversation_tts_to_session(
        self,
        conversation_id: ConversationUUID,
        organization_id: OrganizationUUID,
        payload: dict | str,
    ):
        conversation_id = str(conversation_id)
        organization_id = str(organization_id)
        await self._webrtc_pubsub_manager.publish(
            message={
                "conversation_id": conversation_id,
                "organization_id": organization_id,
                "payload": payload,
            },
        )


def _pubsub_conversation_id(
    envelope: dict,
    *,
    kind: WsEventAction,
) -> UUID | None:
    """Resolve conversation authority from the canonical pubsub envelope."""
    raw_conversation_id = envelope.get("conversation_id")
    if raw_conversation_id is None:
        if kind in _CONVERSATION_SCOPED_PUBSUB_EVENTS:
            raise ValueError(
                f"{kind.value} pubsub message is missing conversation authority."
            )
        return None
    return UUID(str(raw_conversation_id))
