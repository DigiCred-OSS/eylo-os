"""Bridge one browser WebRTC peer to an Agent voice session."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Optional, cast

import arrow
from aiortc import (
    RTCBundlePolicy,
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)

from eylo.common.contracts.websocket import WEBRTC_SIGNALING_VERSION
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.voice import WebRTCState, WebRTCStateEvent
from eylo.pipelines.session_timeline import try_file_runtime_fact
from eylo.pipelines.webrtc.media import IncomingAudioTrack, OutgoingAudioTrack
from eylo.pipelines.websocket.schemas import WSSessionState, WsEventAction

logger = logging.getLogger(__name__)


class AgentPeerClient:
    """Enhanced peer client with STT/TTS audio processing integration."""

    @property
    def pc(self) -> RTCPeerConnection:
        if self._pc:
            return self._pc
        raise ValueError("RTCPeerConnection is not set")

    @property
    def incoming_audio_track(self) -> IncomingAudioTrack:
        if self._incoming_audio_track:
            return self._incoming_audio_track
        raise ValueError("IncomingAudioTrack is not set")

    @property
    def outgoing_audio_track(self) -> OutgoingAudioTrack:
        if self._outgoing_audio_track:
            return self._outgoing_audio_track
        raise ValueError("OutgoingAudioTrack is not set")

    def __init__(
        self,
        session_state: WSSessionState,
        *,
        negotiation_id: str,
        terminal_callback: Callable[[str], Awaitable[None]],
    ):
        self._session_state = session_state
        self._negotiation_id = negotiation_id
        self._terminal_callback = terminal_callback
        self._terminal_scheduled = False
        self._cleaning_up = False
        self._last_timeline_transport_state: str | None = None
        self._pc = None  # Will be set to RTCPeerConnection in setup_peer_connection
        self._outgoing_audio_track = (
            None  # Will be set to OutgoingAudioTrack in setup_peer_connection
        )
        self._incoming_audio_track = (
            None  # Will be set to IncomingAudioTrack if a track is received
        )
        self._consume_task = (
            None  # Will be set to asyncio.Task when track consumption starts
        )
        self._stt_forwarder_task = (
            None  # For draining STT request queue to the STT socket
        )
        self._connection_established_time = (
            None  # Will be set when connection is established
        )
        self._last_activity_time = arrow.utcnow()  # Track when last activity occurred
        self._rtc_configuration = None  # Will be created in setup_peer_connection

    def _emit_webrtc_state(
        self, state: WebRTCState, message: str, data: Optional[dict] = None
    ):
        """Emit WebRTC state change event.

        Args:
            state: WebRTC state enum
            message: Human-readable status message
            data: Additional event data (optional)
        """

        try:
            emit_ephemeral(
                WebRTCStateEvent(
                    state=state,
                    message=message,
                    session_id=self._session_state.session_id,
                    organization_id=self._session_state.organization_id,
                    data=data or {},
                )
            )
            logger.debug(f"Emitted WebRTC {state.value} event")
        except Exception as error:
            logger.warning(
                "WebRTC state event failed state=%s category=%s",
                state.value,
                type(error).__name__,
            )

    def _schedule_terminal(self, reason: str) -> None:
        if self._terminal_scheduled or self._cleaning_up:
            return
        self._terminal_scheduled = True
        asyncio.create_task(self._terminal_callback(reason))

    async def _record_transport_state(self, state: str) -> None:
        if self._last_timeline_transport_state == state:
            return
        self._last_timeline_transport_state = state
        await try_file_runtime_fact(
            organization_id=self._session_state.organization_id,
            user_session_id=self._session_state.user_session_id,
            subject_type="transport.webrtc",
            subject_id=self._session_state.voice_session_id,
            event_type=f"transport.webrtc.{state}",
            payload={"negotiation_id": self._negotiation_id},
        )

    # flake8: noqa
    async def setup_peer_connection(
        self,
        payload: dict,
        *,
        ice_servers: tuple[RTCIceServer, ...],
    ) -> None:
        """Setup the peer connection with audio processing."""
        logger.info("Setting up WebRTC peer connection for STT/TTS")

        # Reset any existing STT forwarder task before creating new queues
        if self._stt_forwarder_task and not self._stt_forwarder_task.done():
            self._stt_forwarder_task.cancel()
            try:
                await self._stt_forwarder_task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                logger.error(
                    "WebRTC STT forwarder reset failed error_type=%s",
                    type(error).__name__,
                )
        self._stt_forwarder_task = None

        self._rtc_configuration = RTCConfiguration(
            iceServers=list(ice_servers), bundlePolicy=RTCBundlePolicy.MAX_BUNDLE
        )

        logger.info(
            f"[WEBRTC] Creating peer connection with {len(ice_servers)} ICE servers"
        )

        self._pc = RTCPeerConnection(configuration=self._rtc_configuration)
        self._last_activity_time = arrow.utcnow()

        # Runtime queues and forwarders are allocated only after config is ready
        # and a peer exists, so failed preparation leaves no background resources.
        if not self._session_state.realtime_mode:
            self._session_state.stt_request_queue = asyncio.Queue(maxsize=50)
        if self._session_state.tts_manager:
            if self._session_state.tts_response_queue is None:
                self._session_state.tts_response_queue = asyncio.Queue(maxsize=1000)
            logger.info("TTS is enabled - will add outgoing audio track")
        elif self._session_state.realtime_mode:
            logger.info("Realtime mode - vendor provides outgoing audio")
        else:
            logger.info("TTS is disabled - STT-only mode")
        if self._session_state.stt_request_queue:
            self._stt_forwarder_task = asyncio.create_task(self._forward_stt_audio())

        # Emit peer created event
        self._emit_webrtc_state(
            state=WebRTCState.PEER_CREATED,
            message="WebRTC peer connection created",
        )

        # Create and add outgoing audio track for TTS (decomposed or realtime mode)
        has_audio_output = (
            self._session_state.tts_manager or self._session_state.realtime_mode
        )
        if has_audio_output:
            self._outgoing_audio_track = OutgoingAudioTrack(self._session_state)
            self.pc.addTrack(self.outgoing_audio_track)
            logger.info("Added outgoing audio track to peer connection")
        else:
            logger.info("TTS disabled - skipping outgoing audio track")

        # Subscribe to connection state changes for monitoring
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"AGENT_PEER: Connection state is {self.pc.connectionState}")
            self._last_activity_time = arrow.utcnow()

            # Emit connection state changes
            state = self.pc.connectionState
            if state == "connecting":
                self._emit_webrtc_state(
                    state=WebRTCState.PEER_CONNECTING,
                    message="WebRTC peer connection is connecting",
                    data={"state": state},
                )
                await self._record_transport_state("connecting")
            elif state == "connected":
                self._connection_established_time = arrow.utcnow()
                self._emit_webrtc_state(
                    state=WebRTCState.PEER_CONNECTED,
                    message="WebRTC peer connection established",
                    data={"state": state},
                )
                await self._record_transport_state("connected")
            elif state == "disconnected":
                self._emit_webrtc_state(
                    state=WebRTCState.PEER_DISCONNECTED,
                    message="WebRTC peer connection disconnected",
                    data={"state": state},
                )
                await self._record_transport_state("disconnected")
                self._schedule_terminal("peer_disconnected")
            elif state in {"failed", "closed"}:
                self._emit_webrtc_state(
                    state=WebRTCState.PEER_FAILED,
                    message="WebRTC peer connection failed",
                    data={"state": state, "error": "Connection failed to establish"},
                )
                await self._record_transport_state(
                    "disconnected" if state == "closed" and self._cleaning_up else "failed"
                )
                self._schedule_terminal(f"peer_{state}")

        @self.pc.on("icegatheringstatechange")
        async def on_icegatheringstatechange():
            logger.info(
                f"AGENT_PEER: ICE gathering state is {self.pc.iceGatheringState}"
            )
            self._last_activity_time = arrow.utcnow()

            # Emit ICE gathering state changes
            state = self.pc.iceGatheringState
            if state == "gathering":
                self._emit_webrtc_state(
                    state=WebRTCState.ICE_GATHERING,
                    message="ICE candidates gathering in progress",
                    data={"state": state},
                )
            elif state == "complete":
                self._emit_webrtc_state(
                    state=WebRTCState.ICE_COMPLETE,
                    message="ICE candidate gathering completed",
                    data={"state": state},
                )

        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info(
                f"AGENT_PEER: ICE connection state is {self.pc.iceConnectionState}"
            )
            self._last_activity_time = arrow.utcnow()

            state = self.pc.iceConnectionState
            if state in {"failed", "disconnected", "closed"}:
                logger.warning(
                    "[ICE_DEBUG] ICE connection state transitioned to %s. "
                    "Relay likely unavailable or connectivity interrupted.",
                    state,
                )
                self._schedule_terminal(f"ice_{state}")

        @self.pc.on("signalingstatechange")
        async def on_signalingstatechange():
            logger.info(f"AGENT_PEER: Signaling state is {self.pc.signalingState}")
            self._last_activity_time = arrow.utcnow()

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            from eylo.pipelines.websocket.singleton import S_ws_manager

            if candidate:
                # Send ICE candidate to client
                try:
                    delivered = await S_ws_manager.send_response(
                        {
                            "kind": WsEventAction.WEBRTC_ICE_CANDIDATE,
                            "data": {
                                "protocol_version": WEBRTC_SIGNALING_VERSION,
                                "command": "candidate",
                                "outcome": "accepted",
                                "negotiation_id": self._negotiation_id,
                                "candidate": {
                                    "candidate": candidate.candidate,
                                    "sdpMid": candidate.sdpMid,
                                    "sdpMLineIndex": candidate.sdpMLineIndex,
                                },
                            },
                        },
                        self._session_state.organization_id,
                        self._session_state.session_id,
                    )
                    if not delivered:
                        self._schedule_terminal("candidate_delivery_failed")
                except Exception as error:
                    logger.warning(
                        "WebRTC candidate delivery failed "
                        "organization_id=%s category=%s",
                        self._session_state.organization_id,
                        type(error).__name__,
                    )
                    self._schedule_terminal("candidate_delivery_failed")
            else:
                logger.info("AGENT_PEER: ICE candidate gathering complete.")
                delivered = await S_ws_manager.send_response(
                    {
                        "kind": WsEventAction.WEBRTC_ICE_CANDIDATE,
                        "data": {
                            "protocol_version": WEBRTC_SIGNALING_VERSION,
                            "command": "candidate",
                            "outcome": "accepted",
                            "negotiation_id": self._negotiation_id,
                            "candidate": None,
                        },
                    },
                    self._session_state.organization_id,
                    self._session_state.session_id,
                )
                if not delivered:
                    self._schedule_terminal("candidate_delivery_failed")

        @self.pc.on("icecandidateerror")
        async def on_icecandidateerror(error):
            logger.warning(
                "WebRTC ICE candidate error organization_id=%s category=%s",
                self._session_state.organization_id,
                type(error).__name__,
            )
            self._last_activity_time = arrow.utcnow()

        # Set up track handler for incoming audio
        @self.pc.on("track")
        def on_track(track):
            logger.info(
                f"Track received: kind={track.kind}, id={getattr(track, 'id', 'unknown')}"
            )
            self._last_activity_time = arrow.utcnow()

            if track.kind == "audio":
                if self._incoming_audio_track is not None:
                    track.stop()
                    self._emit_webrtc_state(
                        state=WebRTCState.PEER_FAILED,
                        message="Additional audio tracks are unsupported in V1",
                        data={"reason": "additional_audio_track"},
                    )
                    self._schedule_terminal("additional_audio_track")
                    return
                # Emit track added event
                self._emit_webrtc_state(
                    state=WebRTCState.TRACK_ADDED,
                    message=f"Audio track added to peer connection",
                    data={
                        "track_kind": track.kind,
                        "track_id": getattr(track, "id", "unknown"),
                    },
                )

                # Wrap incoming track with STT processor
                self._incoming_audio_track = IncomingAudioTrack(
                    track, self._session_state
                )

                # Start consuming the track for STT
                async def consume_track():
                    logger.info("Starting to consume incoming audio track for STT")
                    try:
                        while True:
                            await self.incoming_audio_track.recv()
                            self._last_activity_time = arrow.utcnow()
                    except asyncio.CancelledError:
                        logger.info("Track consumption cancelled")
                        raise
                    except Exception as e:
                        logger.info(
                            "Track consumption ended category=%s", type(e).__name__
                        )
                        self._schedule_terminal("track_ended")
                        return

                self._consume_task = asyncio.create_task(consume_track())

        # Set remote description
        sdp = payload.get("sdp")
        offer_type = payload.get("type", "offer")

        if not sdp:
            raise ValueError("SDP missing")

        offer = RTCSessionDescription(sdp=sdp, type=offer_type)
        await self.pc.setRemoteDescription(offer)

        # Create answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

    async def _forward_stt_audio(self):
        """Drain audio chunks from the session STT queue into the STT socket."""
        queue = self._session_state.stt_request_queue
        if not queue:
            return

        logger.info("AgentPeerClient: STT forwarder task started")
        try:
            while True:
                try:
                    audio_chunk = await queue.get()
                except asyncio.CancelledError:
                    raise

                if audio_chunk is None:
                    queue.task_done()
                    break

                try:
                    stt_socket = self._session_state.stt_socket
                    if stt_socket and self._session_state.stt_started:
                        await stt_socket.send_audio(audio_chunk)
                        # TODO (observability): update `self._session_state.last_activity_at` here so the forwarder keeps the session heartbeat fresh even when audio bypasses the IncomingAudioTrack queue timing.
                    else:
                        logger.debug(
                            "AgentPeerClient: STT socket unavailable, dropping audio chunk"
                        )
                except Exception as error:
                    logger.error(
                        "AgentPeerClient STT forwarding failed error_type=%s",
                        type(error).__name__,
                    )
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            logger.info("AgentPeerClient: STT forwarder task cancelled")
        finally:
            logger.info("AgentPeerClient: STT forwarder task finished")

    async def cleanup(self):
        """Cleanup resources."""
        logger.info("AgentPeerClient.cleanup: starting resource teardown")
        self._cleaning_up = True

        consume_task = cast(Optional[asyncio.Task], self._consume_task)
        if consume_task and not consume_task.done():
            consume_task.cancel()
            try:
                await consume_task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                logger.error(
                    "WebRTC consume task cleanup failed error_type=%s",
                    type(error).__name__,
                )
        self._consume_task = None

        forwarder_task = cast(Optional[asyncio.Task], self._stt_forwarder_task)
        if forwarder_task and not forwarder_task.done():
            forwarder_task.cancel()
            try:
                await forwarder_task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                logger.error(
                    "WebRTC STT forwarder cleanup failed error_type=%s",
                    type(error).__name__,
                )
        self._stt_forwarder_task = None

        # Stop incoming audio track and clear buffers
        if self._incoming_audio_track:
            try:
                if self._incoming_audio_track.downsampler:
                    self._incoming_audio_track.downsampler.clear_buffers()
            except Exception as error:
                logger.warning(
                    "AgentPeerClient cleanup failed to clear incoming downsampler "
                    "buffers error_type=%s",
                    type(error).__name__,
                )

            try:
                self._incoming_audio_track.stop()
            except Exception as error:
                logger.warning(
                    "AgentPeerClient cleanup failed to stop incoming track "
                    "error_type=%s",
                    type(error).__name__,
                )
            finally:
                self._incoming_audio_track = None

        # Stop outgoing audio track and clear queued audio
        if self._outgoing_audio_track:
            try:
                await self._outgoing_audio_track.clear_buffers()
            except Exception as error:
                logger.warning(
                    "AgentPeerClient cleanup failed to clear outgoing buffers "
                    "error_type=%s",
                    type(error).__name__,
                )

            try:
                self._outgoing_audio_track.stop()
            except Exception as error:
                logger.warning(
                    "AgentPeerClient cleanup failed to stop outgoing track "
                    "error_type=%s",
                    type(error).__name__,
                )
            finally:
                self._outgoing_audio_track = None

        # Close peer connection if still open
        if self._pc:
            try:
                await self._pc.close()
            except Exception as error:
                logger.warning(
                    "AgentPeerClient cleanup failed to close RTCPeerConnection "
                    "error_type=%s",
                    type(error).__name__,
                )
            finally:
                self._pc = None

        # Reset session queues/events to avoid leaking state across sessions
        try:
            if self._session_state.stt_request_queue:
                queue = self._session_state.stt_request_queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                self._session_state.stt_request_queue = None

            if (
                self._session_state.tts_response_queue
                and not self._session_state.tts_manager
                and not self._session_state.realtime_mode
            ):
                queue = self._session_state.tts_response_queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                self._session_state.tts_response_queue = None

            if self._session_state.tts_interrupt_event.is_set():
                self._session_state.tts_interrupt_event.clear()
        except Exception as error:
            logger.warning(
                "AgentPeerClient cleanup failed to reset session state error_type=%s",
                type(error).__name__,
            )

        logger.info("AgentPeerClient.cleanup: resource teardown complete")
