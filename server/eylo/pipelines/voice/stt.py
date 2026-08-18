"""Resolved streaming STT runtime construction."""

import asyncio
import logging
from typing import Callable
from uuid import UUID

import arrow

from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.voice import STTState, STTStateEvent
from eylo.runtime.tasks import monitor_long_running_tasks, teardown_long_running_tasks
from eylo.sockets.stt.events import normalize_stt_event
from eylo.sockets.stt.exceptions import (
    STTConnectionError,
    STTConnectionFailed,
)
from eylo.sockets.stt.factory import STTFactory
from eylo.sockets.stt.schemas import (
    STTConfig,
    STTEvent,
    STTEventType,
    STTMetricsSnapshot,
)

"""STT Realtime Socket Handler with Turn-Based Conversation Support

This module handles the socket connection for real-time speech-to-text (STT) processing
with enhanced capabilities for turn-based conversations:
1. Speech activity detection via VAD events
2. Turn detection through SpeechStarted and UtteranceEnd events
3. Final transcript collection for completed turns
4. Queue management with robust error recovery
"""


_KEEPALIVE_INTERVAL = 5  # seconds

logger = logging.getLogger(__name__)


class STTRealtime:
    """Real-time speech-to-text service with turn-based conversation support.

    This class manages the communication with the STT service, providing:
    1. Audio data streaming to Deepgram
    2. Turn-based conversation handling with proper VAD
    3. Transcript collection for completed turns
    4. Queue management with backpressure detection
    5. Health monitoring and metrics
    6. Graceful error recovery
    """

    _REQUEST_QUEUE_TIMEOUT = 5  # seconds
    _MAX_QUEUE_SIZE = 100  # Example maximum size for the queues
    _JOIN_TIMEOUT = 10  # seconds
    _HEALTH_CHECK_INTERVAL = 5  # seconds
    _BACKPRESSURE_THRESHOLD = 0.8  # 80% fullness
    _MAX_BUFFER_SEGMENTS = 50  # Safety cap for debouncing

    def __init__(
        self,
        organization_id: UUID,
        session_id: str,
        consumer_queue: asyncio.Queue,
        stt_config: STTConfig | dict | None = None,
        stt_vendor: str | None = None,
        *,
        api_key: str | None = None,
    ):
        """Initialize the real-time STT service.

        Args:
            organization_id: Organization ID
            session_id: Session ID
            consumer_queue: Queue for responses
            stt_config: Configuration for the STT service
            stt_vendor: STT service provider ("deepgram", "deepgram_flux", etc.)
            api_key: Optional resolved API key from organization-scoped config.

        """
        self._typed_config = STTConfig.from_mapping(
            stt_config,
            vendor=stt_vendor,
        )
        self._stt_vendor = self._typed_config.vendor
        self._organization_id = organization_id
        self._session_id = session_id

        self._respond_back_queue = consumer_queue

        self._stt_service_results = asyncio.Queue(maxsize=self._MAX_QUEUE_SIZE)

        stt_config_dict = self._typed_config.to_adapter_config()
        # Convert incoming wait_ms (milliseconds) to float seconds for asyncio.sleep
        self._wait_seconds = float(stt_config_dict.get("wait_ms", 0)) / 1000.0
        self._transcript_buffer = []
        self._wait_task = None
        self._metrics = STTMetricsSnapshot()

        # Create STT factory
        self._stt_factory = STTFactory(
            organization_id,
            session_id,
            consumer_queue=self._stt_service_results,
            stt_config=stt_config_dict,
            stt_vendor=self._stt_vendor,
            api_key=api_key,
        )

    def _emit_stt_state(self, state: STTState, message: str, data: dict | None = None):
        """Helper to emit STT state changes via event system.

        Args:
            state: STT state enum
            message: Human-readable status message
            data: Optional additional data for the event

        """
        try:
            emit_ephemeral(
                STTStateEvent(
                    state=state,
                    message=message,
                    vendor=self._stt_vendor,
                    session_id=self._session_id,
                    organization_id=self._organization_id,
                    data=data or {},
                )
            )
            logger.debug(f"Emitted STT state event: {state.value}")
        except Exception as error:
            logger.error(
                "STT state event emission failed state=%s error_type=%s",
                state.value,
                type(error).__name__,
            )

    @property
    def is_connected(self) -> bool:
        """Check if the underlying STT service is connected."""
        return self._stt_factory.is_connected

    @property
    def metrics(self) -> dict:
        """Get current lightweight manager metrics."""
        snapshot = self._metrics.as_dict()
        snapshot["factory"] = self._stt_factory.metrics
        return snapshot

    @staticmethod
    def _is_retryable_send_disconnect(error: Exception) -> bool:
        if isinstance(error, STTConnectionError):
            return True
        if isinstance(error, RuntimeError):
            return "not connected" in str(error).lower()
        return False

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to the STT service for speech recognition.

        Args:
            audio_data: Raw audio bytes (typically 16kHz PCM format)

        """
        try:
            self._metrics.mark_audio_sent(len(audio_data))
            await self._stt_factory.service.send_audio(audio_data)
        except Exception as error:
            self._metrics.mark_error()
            if not self._is_retryable_send_disconnect(error):
                raise

            logger.warning(
                "STT send path lost connection for session %s (%s). "
                "Reconnecting and retrying once.",
                self._session_id,
                type(error).__name__,
            )
            await self._stt_factory.reconnect()
            self._metrics.mark_reconnect()
            await self._stt_factory.service.send_audio(audio_data)

    async def _await_response(self):
        """Get the processed response from the response queue."""
        response = None
        try:
            response = await asyncio.wait_for(
                self._stt_service_results.get(),
                self._REQUEST_QUEUE_TIMEOUT,
            )
            if response:
                self._stt_service_results.task_done()
        except asyncio.TimeoutError:
            pass
        except asyncio.QueueEmpty:
            pass
        except Exception as error:
            logger.error(
                "STT response wait failed error_type=%s",
                type(error).__name__,
            )
            raise
        return response

    async def _handle_response_for_consumer(self, event: STTEvent) -> None:
        """Project a canonical STT event onto the websocket voice contract."""
        self._metrics.mark_event(event.type.value)
        normalized_response = normalize_stt_event(event)
        transcript_chars = len(str(normalized_response.get("transcript") or ""))
        logger.info(
            "STTRealtime forwarding type=%s final=%s transcript_chars=%d",
            normalized_response.get("type"),
            normalized_response.get("is_final"),
            transcript_chars,
        )

        if self._wait_seconds <= 0:
            self._respond_back_queue.put_nowait(normalized_response)
            return

        response_type = normalized_response.get("type")
        if response_type == "transcript" and normalized_response.get("is_final"):
            new_segment = normalized_response.get("transcript", "")
            self._transcript_buffer.append(new_segment)
            logger.debug(
                "[STT_WAIT] Added segment chars=%d buffer_segments=%d",
                len(new_segment),
                len(self._transcript_buffer),
            )

            if self._wait_task and not self._wait_task.done():
                self._wait_task.cancel()
                logger.debug("[STT_WAIT] Resetting timer on transcript")

            if len(self._transcript_buffer) >= self._MAX_BUFFER_SEGMENTS:
                logger.warning("[STT_WAIT] Max buffer segments reached. Forcing flush.")
                await self._flush_transcript_buffer()
            else:
                self._wait_task = asyncio.create_task(self._run_wait_timer())
            return

        if response_type == STTEventType.VAD.value:
            if self._wait_task and not self._wait_task.done():
                self._wait_task.cancel()
                logger.debug("[STT_WAIT] Resetting timer on %s", response_type)

            self._wait_task = asyncio.create_task(self._run_wait_timer())
            logger.info(
                "[STT_WAIT] VAD event detected. Forwarding immediately "
                "(buffer size: %d)",
                len(self._transcript_buffer),
            )
            self._respond_back_queue.put_nowait(normalized_response)
            return

        self._respond_back_queue.put_nowait(normalized_response)

    async def initialize(self) -> None:
        """Run STT and surface every fatal startup/runtime failure to the client."""
        try:
            await self._run()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._emit_stt_state(
                state=STTState.ERROR,
                message="STT service failed",
                data={"error_type": type(error).__name__},
            )
            logger.error(
                "STT service terminated error_type=%s",
                type(error).__name__,
            )
            raise

    async def _run(self) -> None:
        """Process audio data in real-time through the STT service.

        This method establishes a connection to the STT service and sets up multiple
        concurrent tasks to handle different aspects of audio processing:
        - Sending keepalive signals to maintain the connection
        - Processing audio requests from the queue
        - Receiving and handling responses from the STT service
        - Monitoring health and detecting turn completion events
        """
        # Emit connecting state
        self._emit_stt_state(
            state=STTState.CONNECTING,
            message="Connecting to STT service",
        )

        async with self._stt_factory.connection():
            # Emit connected state
            self._emit_stt_state(
                state=STTState.CONNECTED,
                message="STT service connected",
            )

            async def _respond_to_consumer():
                """Send processed responses to the client."""
                try:
                    while True:
                        try:
                            response = await self._await_response()
                            if response:
                                await self._handle_response_for_consumer(response)
                        except asyncio.TimeoutError:
                            # Timeout waiting for response - continue
                            continue
                except asyncio.CancelledError:
                    # Allow cancellation to propagate for clean shutdown
                    raise
                except Exception as error:
                    logger.error(
                        "STT consumer forwarding failed error_type=%s",
                        type(error).__name__,
                    )
                    raise  # Re-raise to trigger task restart

            # Dictionary mapping task names to their coroutine functions
            task_definitions: dict[str, Callable] = {
                "stt_rt_response": _respond_to_consumer,
            }

            # Initialize active tasks dictionary
            active_tasks: dict[str, asyncio.Task] = {}
            for name, coro in task_definitions.items():
                active_tasks[name] = asyncio.create_task(coro())

            try:
                # Emit ready state
                self._emit_stt_state(
                    state=STTState.READY,
                    message="STT service ready to process audio",
                )

                # Main task monitoring loop
                while True:
                    await monitor_long_running_tasks(
                        task_definitions=task_definitions,
                        active_tasks=active_tasks,
                        exceptions_to_ignore={asyncio.CancelledError},
                        exceptions_to_restart={STTConnectionFailed},
                    )
                    await asyncio.sleep(self._HEALTH_CHECK_INTERVAL)

            except asyncio.CancelledError:
                pass
            except Exception as error:
                logger.error(
                    "STT runtime failed error_type=%s",
                    type(error).__name__,
                )
                raise
            finally:
                await self.disconnect()
                await teardown_long_running_tasks(active_tasks=active_tasks)

    async def disconnect(self):
        """Disconnect from the STT service and clean up resources."""
        # Emit disconnected state BEFORE actually disconnecting
        # to ensure the WebSocket connection is still active
        self._emit_stt_state(
            state=STTState.DISCONNECTED,
            message="STT service disconnected",
        )

        # Cleanup wait mechanism (T6)
        if self._wait_task and not self._wait_task.done():
            self._wait_task.cancel()
            logger.info("[STT_WAIT] Cancelled active wait task during disconnect")

        if self._transcript_buffer:
            logger.info("[STT_WAIT] Performing final flush during disconnect")
            await self._flush_transcript_buffer()

        await self._stt_factory.disconnect()

        logger.info("Disconnected from STT service.")

    async def _flush_transcript_buffer(self):
        """Join all buffered transcripts and send them to the consumer."""
        if not self._transcript_buffer:
            return

        # Combine all segments into one string
        combined_transcript = " ".join(self._transcript_buffer).strip()

        # Reset the buffer immediately to prevent race conditions
        self._transcript_buffer = []

        if combined_transcript:
            logger.info(
                "[STT_WAIT] Sending combined transcript chars=%d",
                len(combined_transcript),
            )
            # Create a response object that matches what our consumers expect
            response = {
                "type": "transcript",
                "transcript": combined_transcript,
                "is_final": True,
                "timestamp": arrow.utcnow().timestamp(),
            }

            # Push it to the final queue
            try:
                self._respond_back_queue.put_nowait(response)
            except asyncio.QueueFull:
                logger.warning("Response queue is full, discarding response")

        # Clean up the task reference
        self._wait_task = None

    async def _run_wait_timer(self):
        """Wait for the specified period and then flush the buffer."""
        try:
            # Wait for the specified silence duration
            await asyncio.sleep(self._wait_seconds)

            # If we get here, it means the silence duration has elapsed. Flush the buffer
            await self._flush_transcript_buffer()

        except asyncio.CancelledError:
            # This is the "reset" mechanism.
            # When a new transcript arrives, we will cancel this task.
            pass
        except Exception as error:
            logger.error(
                "STT wait timer failed error_type=%s",
                type(error).__name__,
            )
            self._wait_task = None
