"""Tenant-bound WebRTC signaling and lifecycle ownership."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from aiortc import RTCIceCandidate

from eylo.common.config import settings
from eylo.common.contracts.websocket import WEBRTC_SIGNALING_VERSION
from eylo.pipelines.webrtc.agent_peer import AgentPeerClient
from eylo.pipelines.webrtc.config import (
    browser_ice_servers,
    resolve_ice_configuration,
)
from eylo.pipelines.webrtc.ice_policy import (
    IceCandidateError,
    IceDeploymentMode,
    filter_offer_candidates,
    parse_remote_candidate,
)
from eylo.pipelines.webrtc.playback import (
    needs_tts_streamer,
    start_tts_streamer,
    stop_tts_streamer,
)
from eylo.pipelines.webrtc.schemas import (
    WebRTCNegotiationState,
    WebRTCSession,
    WebRTCSessionKey,
)
from eylo.pipelines.websocket.schemas import WsEventAction, WsRequestEvent

logger = logging.getLogger(__name__)

WEBRTC_PROTOCOL_VERSION = WEBRTC_SIGNALING_VERSION
NEGOTIATION_DEADLINE_SECONDS = 30
MAX_REMOTE_CANDIDATES = 128


class WebRTCSignalingError(RuntimeError):
    """Safe, typed signaling failure returned at the interface boundary."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class WebRTCSignalingManager:
    """Own one negotiation aggregate per organization and auth session."""

    def __init__(self) -> None:
        self._sessions: dict[WebRTCSessionKey, WebRTCSession] = {}
        self._registry_lock = asyncio.Lock()

    async def start(self) -> None:
        logger.info("WebRTC signaling manager started")

    async def stop(self) -> None:
        for key in list(self._sessions):
            await self.cleanup_session(
                key.organization_id,
                key.session_id,
                reason="shutdown",
            )
        logger.info("WebRTC signaling manager stopped")

    def get_session(
        self, organization_id: UUID, session_id: str
    ) -> WebRTCSession | None:
        """Return an exact tenant-bound session for composition and probes."""
        return self._sessions.get(WebRTCSessionKey(organization_id, session_id))

    async def prepare_session(
        self,
        organization_id: UUID,
        session_id: str,
    ) -> dict[str, Any]:
        """Resolve org ICE config before the browser constructs its peer."""
        from eylo.pipelines.websocket.singleton import S_ws_manager

        key = WebRTCSessionKey(organization_id, session_id)
        session_state = S_ws_manager.get_session_state(organization_id, session_id)
        if session_state is None:
            raise WebRTCSignalingError("session_not_found")

        async with self._registry_lock:
            session = self._sessions.get(key)
            if session is None:
                session = WebRTCSession(
                    key=key,
                    session_state=session_state,
                    negotiation_id=str(uuid4()),
                )
                self._sessions[key] = session

        failure: Exception | None = None
        async with session.lock:
            if session.state is WebRTCNegotiationState.PREPARING:
                try:
                    resolved_ice = await resolve_ice_configuration(session_state)
                    session.ice_servers = resolved_ice.ice_servers
                    session.credential_expires_at = resolved_ice.credential_expires_at
                    session.negotiation_expires_at = (
                        time.time() + NEGOTIATION_DEADLINE_SECONDS
                    )
                    session.transition(WebRTCNegotiationState.PREPARED)
                    session.deadline_task = asyncio.create_task(
                        self._expire_negotiation(key, session.negotiation_id)
                    )
                except Exception as error:
                    failure = error
            elif session.state in {
                WebRTCNegotiationState.TERMINATING,
                WebRTCNegotiationState.TERMINATED,
            }:
                raise WebRTCSignalingError("negotiation_terminated")

            if failure is None:
                return {
                    "protocol_version": WEBRTC_PROTOCOL_VERSION,
                    "command": "prepare",
                    "outcome": "accepted",
                    "negotiation_id": session.negotiation_id,
                    "negotiation_expires_at": session.negotiation_expires_at,
                    "credential_expires_at": session.credential_expires_at,
                    "iceServers": browser_ice_servers(session.ice_servers),
                }

        await self._terminal_cleanup(key, "prepare_failed")
        if failure is None:
            raise WebRTCSignalingError("prepare_failed")
        raise failure

    async def handle_offer(
        self,
        organization_id: UUID,
        session_id: str,
        payload: WsRequestEvent,
    ) -> None:
        """Acquire one offer, publish only after its answer is delivered."""
        from eylo.pipelines.websocket.singleton import S_ws_manager

        data = payload.data or {}
        negotiation_id = _required_string(data, "negotiation_id")
        sdp = _required_string(data, "sdp")
        _require_protocol_version(data)

        key = WebRTCSessionKey(organization_id, session_id)
        session = self._sessions.get(key)
        if session is None:
            raise WebRTCSignalingError("prepare_required")
        offer_digest = hashlib.sha256(sdp.encode()).hexdigest()

        failure: Exception | None = None
        cleanup_on_failure = False
        async with session.lock:
            try:
                if negotiation_id != session.negotiation_id:
                    raise WebRTCSignalingError("negotiation_mismatch")
                if session.state is WebRTCNegotiationState.ACTIVE:
                    if (
                        session.offer_digest != offer_digest
                        or session.answer_payload is None
                    ):
                        raise WebRTCSignalingError("offer_conflict")
                    delivered = await S_ws_manager.send_response(
                        _signal_envelope(
                            WsEventAction.WEBRTC_ANSWER,
                            session.answer_payload,
                            request_id=payload.request_id,
                        ),
                        organization_id,
                        session_id,
                    )
                    if not delivered:
                        cleanup_on_failure = True
                        raise WebRTCSignalingError("answer_delivery_failed")
                    return
                if session.state is not WebRTCNegotiationState.PREPARED:
                    raise WebRTCSignalingError("negotiation_unavailable")

                session.transition(WebRTCNegotiationState.ACQUIRING)
                cleanup_on_failure = True
                sanitized_data = dict(data)
                try:
                    sanitized_data["sdp"] = filter_offer_candidates(
                        sdp,
                        mode=_deployment_mode(),
                        max_candidates=MAX_REMOTE_CANDIDATES,
                    )
                except IceCandidateError as error:
                    raise WebRTCSignalingError(error.code) from None
                embedded_digests = {
                    hashlib.sha256(line.removeprefix("a=").encode()).hexdigest()
                    for line in sanitized_data["sdp"].splitlines()
                    if line.startswith("a=candidate:")
                }
                if (
                    len(session.candidate_digests | embedded_digests)
                    > MAX_REMOTE_CANDIDATES
                ):
                    raise WebRTCSignalingError("candidate_limit_reached")
                session.candidate_digests.update(embedded_digests)
                peer_client = AgentPeerClient(
                    session.session_state,
                    negotiation_id=session.negotiation_id,
                    terminal_callback=lambda reason: self._terminal_cleanup(
                        key, reason
                    ),
                )
                session.peer_client = peer_client
                await peer_client.setup_peer_connection(
                    sanitized_data,
                    ice_servers=session.ice_servers,
                )
                for candidate in session.pending_candidates:
                    await peer_client.pc.addIceCandidate(candidate)
                session.pending_candidates.clear()

                local_description = peer_client.pc.localDescription
                if local_description is None:
                    raise WebRTCSignalingError("answer_unavailable")
                answer_payload = {
                    "protocol_version": WEBRTC_PROTOCOL_VERSION,
                    "command": "answer",
                    "outcome": "accepted",
                    "negotiation_id": session.negotiation_id,
                    "sdp": local_description.sdp,
                    "type": local_description.type,
                }
                delivered = await S_ws_manager.send_response(
                    _signal_envelope(
                        WsEventAction.WEBRTC_ANSWER,
                        answer_payload,
                        request_id=payload.request_id,
                    ),
                    organization_id,
                    session_id,
                )
                if not delivered:
                    raise WebRTCSignalingError("answer_delivery_failed")

                session.answer_payload = answer_payload
                session.offer_digest = offer_digest
                session.transition(WebRTCNegotiationState.ACTIVE)
                _cancel_deadline(session)
                if needs_tts_streamer(session.session_state):
                    session.tts_streamer_task = start_tts_streamer(
                        organization_id=organization_id,
                        session_id=session_id,
                    )
                logger.info(
                    "WebRTC negotiation active organization_id=%s",
                    organization_id,
                )
            except Exception as error:
                failure = error

        if failure is not None:
            if cleanup_on_failure:
                await self._terminal_cleanup(key, "offer_failed")
            raise failure

    async def handle_candidate(
        self,
        organization_id: UUID,
        session_id: str,
        payload: WsRequestEvent,
    ) -> dict[str, Any]:
        """Admit, deduplicate, cap, and apply one remote ICE candidate."""
        data = payload.data or {}
        _require_protocol_version(data)
        negotiation_id = _required_string(data, "negotiation_id")
        key = WebRTCSessionKey(organization_id, session_id)
        session = self._sessions.get(key)
        if session is None:
            raise WebRTCSignalingError("prepare_required")

        candidate_data = data.get("candidate")
        if isinstance(candidate_data, dict) and isinstance(
            candidate_data.get("candidate"), dict
        ):
            candidate_data = candidate_data["candidate"]

        async with session.lock:
            if negotiation_id != session.negotiation_id:
                raise WebRTCSignalingError("negotiation_mismatch")
            if session.state not in {
                WebRTCNegotiationState.PREPARED,
                WebRTCNegotiationState.ACQUIRING,
                WebRTCNegotiationState.ACTIVE,
            }:
                raise WebRTCSignalingError("negotiation_unavailable")

            if candidate_data is None:
                candidate: RTCIceCandidate | None = None
                digest = "end-of-candidates"
            else:
                if not isinstance(candidate_data, dict):
                    raise WebRTCSignalingError("malformed_candidate")
                candidate_line = candidate_data.get("candidate")
                if not isinstance(candidate_line, str):
                    raise WebRTCSignalingError("malformed_candidate")
                digest = hashlib.sha256(candidate_line.encode()).hexdigest()
                if digest in session.candidate_digests:
                    return _candidate_outcome(session, duplicate=True)
                try:
                    parsed = parse_remote_candidate(
                        candidate_line,
                        mode=_deployment_mode(),
                    )
                except IceCandidateError as error:
                    raise WebRTCSignalingError(error.code) from None
                sdp_mid = candidate_data.get("sdpMid")
                sdp_mline_index = candidate_data.get("sdpMLineIndex")
                if sdp_mid is not None and not isinstance(sdp_mid, str):
                    raise WebRTCSignalingError("malformed_candidate")
                if sdp_mline_index is not None and (
                    not isinstance(sdp_mline_index, int)
                    or isinstance(sdp_mline_index, bool)
                    or sdp_mline_index < 0
                ):
                    raise WebRTCSignalingError("malformed_candidate")
                candidate = RTCIceCandidate(
                    foundation=parsed.foundation,
                    component=parsed.component,
                    protocol=parsed.protocol,
                    priority=parsed.priority,
                    ip=parsed.address,
                    port=parsed.port,
                    type=parsed.candidate_type,
                    relatedAddress=parsed.related_address,
                    relatedPort=parsed.related_port,
                    sdpMid=sdp_mid,
                    sdpMLineIndex=sdp_mline_index,
                    tcpType=parsed.tcp_type,
                )

            if digest in session.candidate_digests:
                return _candidate_outcome(session, duplicate=True)
            if len(session.candidate_digests) >= MAX_REMOTE_CANDIDATES:
                raise WebRTCSignalingError("candidate_limit_reached")
            session.candidate_digests.add(digest)

            if session.peer_client is None:
                session.pending_candidates.append(candidate)
            else:
                try:
                    await session.peer_client.pc.addIceCandidate(candidate)
                except Exception:
                    raise WebRTCSignalingError("candidate_apply_failed") from None
            return _candidate_outcome(session, duplicate=False)

    async def cleanup_session(
        self,
        organization_id: UUID,
        session_id: str,
        *,
        reason: str = "hangup",
        notify_client: bool = False,
    ) -> bool:
        """Run terminal cleanup once; every teardown step is failure-contained."""
        from eylo.pipelines.websocket.singleton import S_ws_manager

        key = WebRTCSessionKey(organization_id, session_id)
        session = self._sessions.get(key)
        if session is None:
            return False

        owns_cleanup = False
        try:
            async with session.lock:
                if session.state in {
                    WebRTCNegotiationState.TERMINATING,
                    WebRTCNegotiationState.TERMINATED,
                }:
                    return False
                owns_cleanup = True
                session.transition(WebRTCNegotiationState.TERMINATING)
                _cancel_deadline(session)

                if notify_client:
                    try:
                        await S_ws_manager.send_response(
                            _signal_envelope(
                                WsEventAction.WEBRTC_HANGUP,
                                {
                                    "protocol_version": WEBRTC_PROTOCOL_VERSION,
                                    "command": "hangup",
                                    "outcome": "accepted",
                                    "negotiation_id": session.negotiation_id,
                                    "reason": reason,
                                },
                            ),
                            organization_id,
                            session_id,
                        )
                    except Exception as error:
                        _log_cleanup_failure(organization_id, "notify", error)

                try:
                    await stop_tts_streamer(
                        session.tts_streamer_task,
                        session_id=session_id,
                    )
                except Exception as error:
                    _log_cleanup_failure(organization_id, "tts_streamer", error)
                finally:
                    session.tts_streamer_task = None

                if session.peer_client is not None:
                    try:
                        await session.peer_client.cleanup()
                    except Exception as error:
                        _log_cleanup_failure(organization_id, "peer", error)
                    finally:
                        session.peer_client = None

                session.pending_candidates.clear()
                session.candidate_digests.clear()
                session.transition(WebRTCNegotiationState.TERMINATED)
        finally:
            if owns_cleanup:
                await self._detach(key, session)

        logger.info(
            "WebRTC session cleaned organization_id=%s reason=%s",
            organization_id,
            reason,
        )
        return True

    async def _terminal_cleanup(self, key: WebRTCSessionKey, reason: str) -> None:
        session = self._sessions.get(key)
        terminal_callback = (
            session.session_state.voice_terminal_callback if session else None
        )
        cleaned = await self.cleanup_session(
            key.organization_id,
            key.session_id,
            reason=reason,
            notify_client=True,
        )
        if cleaned and terminal_callback is not None:
            try:
                await terminal_callback(reason)
            except Exception as error:
                _log_cleanup_failure(key.organization_id, "voice_runtime", error)

    async def _expire_negotiation(
        self,
        key: WebRTCSessionKey,
        negotiation_id: str,
    ) -> None:
        try:
            await asyncio.sleep(NEGOTIATION_DEADLINE_SECONDS)
            session = self._sessions.get(key)
            if session is None or session.negotiation_id != negotiation_id:
                return
            await self._terminal_cleanup(key, "negotiation_timeout")
        except asyncio.CancelledError:
            raise

    async def _detach(self, key: WebRTCSessionKey, session: WebRTCSession) -> None:
        async with self._registry_lock:
            if self._sessions.get(key) is session:
                self._sessions.pop(key, None)


def _deployment_mode() -> IceDeploymentMode:
    return (
        IceDeploymentMode.LOCAL
        if settings.ENV.value == "local"
        else IceDeploymentMode.PUBLIC
    )


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise WebRTCSignalingError(f"missing_{field}")
    return value


def _require_protocol_version(data: dict[str, Any]) -> None:
    if data.get("protocol_version") != WEBRTC_PROTOCOL_VERSION:
        raise WebRTCSignalingError("unsupported_protocol_version")


def _signal_envelope(
    kind: WsEventAction,
    data: dict[str, Any],
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {"kind": kind, "request_id": request_id, "data": data}


def _candidate_outcome(
    session: WebRTCSession,
    *,
    duplicate: bool,
) -> dict[str, Any]:
    return {
        "protocol_version": WEBRTC_PROTOCOL_VERSION,
        "command": "candidate",
        "outcome": "accepted",
        "negotiation_id": session.negotiation_id,
        "duplicate": duplicate,
    }


def _cancel_deadline(session: WebRTCSession) -> None:
    task = session.deadline_task
    if task is not None and task is not asyncio.current_task() and not task.done():
        task.cancel()
    session.deadline_task = None


def _log_cleanup_failure(
    organization_id: UUID,
    step: str,
    error: Exception,
) -> None:
    logger.warning(
        "WebRTC cleanup step failed organization_id=%s step=%s category=%s",
        organization_id,
        step,
        type(error).__name__,
    )
