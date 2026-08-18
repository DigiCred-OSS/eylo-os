"""Resolved streaming TTS runtime construction."""

import asyncio
import logging
import time
from typing import Any, Callable
from uuid import UUID

import arrow

from eylo.common.contracts.voice import VoiceSpeechOutcome
from eylo.events.py_events.emitter import emit_ephemeral
from eylo.events.schema.py_events.voice import TTSState, TTSStateEvent
from eylo.runtime.tasks import (
    monitor_long_running_tasks,
    teardown_long_running_tasks,
    teardown_queues,
)
from eylo.sockets.tts.exceptions import TTSConnectionClosed, TTSConnectionFailed
from eylo.sockets.tts.factory import TTSFactory
from eylo.sockets.tts.schemas import (
    TTSAudioChunk,
    TTSAudioFormat,
    TTSConfig,
    TTSMetricsSnapshot,
    normalize_tts_config,
)
from eylo.sockets.tts.text_stream import (
    SpeakableTextBuffer,
    has_speakable_text,
    normalize_tts_text,
)

logger = logging.getLogger(__name__)


class TTSRealtime:
    _REQUEST_QUEUE_TIMEOUT = (
        2  # seconds (reduced from 5 for faster voice pipeline responsiveness)
    )
    _MAX_QUEUE_SIZE = 1000
    _JOIN_TIMEOUT = 2  # seconds (reduced from 5 for faster shutdown)
    _HEALTH_CHECK_INTERVAL = 2  # seconds (reduced from 5 for faster task monitoring)
    _KEEPALIVE_INTERVAL = 5  # seconds
    _PLAYBACK_ACTIVITY_GRACE_SECONDS = 1.0

    def __init__(
        self,
        organization_id: UUID,
        session_id: str,
        consumer_queue: asyncio.Queue,
        tts_config: TTSConfig | dict[str, Any],
        on_audio_chunk: "Callable[[bytes], None] | None" = None,
        on_playback_started: Callable[[], None] | None = None,
        on_playback_finished: Callable[[], None] | None = None,
        on_turn_outcome: Callable[[str | None, VoiceSpeechOutcome], None] | None = None,
        *,
        api_key: str | None = None,
    ):
        self._organization_id = organization_id
        self._session_id = session_id
        self._request_queue = asyncio.Queue(maxsize=self._MAX_QUEUE_SIZE)
        self._response_queue = asyncio.Queue(maxsize=self._MAX_QUEUE_SIZE)
        self._typed_tts_config = normalize_tts_config(tts_config)
        self._tts_config = self._typed_tts_config.to_adapter_config()
        self._consumer_queue = consumer_queue
        self._on_audio_chunk = on_audio_chunk
        self._on_playback_started = on_playback_started
        self._on_playback_finished = on_playback_finished
        self._on_turn_outcome = on_turn_outcome
        # Connection state
        self._is_connected = False

        self._active_turn_id: str | None = None
        self._queued_turn_id: str | None = None
        self._active_request_id: str | None = None
        self._queued_request_id: str | None = None
        self._text_buffer = SpeakableTextBuffer()

        # Playback completion signaling
        self._playback_done: asyncio.Event = asyncio.Event()
        self._playback_done.set()
        self._playback_error: Exception | None = None
        self._awaiting_playback_completion = False
        self._received_audio_for_turn = False
        self._sent_text_for_turn = False
        self._last_audio_chunk_at = 0.0
        self._last_playback_activity_at = 0.0

        # Init
        self._tts_vendor = self._tts_config["vendor"]

        self._tts_factory = TTSFactory(
            tts_vendor=self._tts_vendor, tts_config=self._tts_config, api_key=api_key
        )

        # Metrics
        self._metrics = {
            "request_drops": 0,
            "response_drops": 0,
            "consumer_drops": 0,
            "errors": 0,
            "interruptions": 0,
            "audio_chunks": 0,
            "audio_bytes": 0,
            "first_audio_latency_seconds": None,
            "total_requests_processed": 0,
            "total_responses_processed": 0,
            "start_time": arrow.utcnow().timestamp(),
            "last_activity": arrow.utcnow().timestamp(),
        }
        self._first_text_sent_at: float | None = None

    @property
    def consumer_queue(self) -> asyncio.Queue:
        """Queue that receives synthesized audio for downstream playback."""
        return self._consumer_queue

    @property
    def is_connected(self) -> bool:
        """Return whether the provider connection is ready for requests."""
        return self._is_connected

    @property
    def active_request_id(self) -> str | None:
        return self._active_request_id

    @property
    def queued_request_id(self) -> str | None:
        return self._queued_request_id

    @property
    def output_audio_format(self) -> TTSAudioFormat:
        """Actual provider output, independent of downstream transport needs."""
        return self._tts_factory.service.output_audio_format

    def metrics_snapshot(self) -> TTSMetricsSnapshot:
        """Return a typed snapshot of current TTS runtime metrics."""
        return TTSMetricsSnapshot(
            vendor=self._tts_vendor,
            chunks=self._metrics["audio_chunks"],
            bytes=self._metrics["audio_bytes"],
            first_audio_latency_seconds=self._metrics["first_audio_latency_seconds"],
            interruptions=self._metrics["interruptions"],
            request_drops=self._metrics["request_drops"],
            response_drops=self._metrics["response_drops"],
            consumer_drops=self._metrics["consumer_drops"],
            errors=self._metrics["errors"],
            total_requests_processed=self._metrics["total_requests_processed"],
            total_responses_processed=self._metrics["total_responses_processed"],
            start_time=self._metrics["start_time"],
            last_activity=self._metrics["last_activity"],
        )

    def _emit_tts_state(self, state: TTSState, message: str, data: dict = None):
        """Helper to emit TTS state changes via event system.

        Args:
            state: TTS state enum
            message: Human-readable status message
            data: Optional additional data for the event

        """
        try:
            emit_ephemeral(
                TTSStateEvent(
                    state=state,
                    message=message,
                    vendor=self._tts_vendor,
                    session_id=self._session_id,
                    organization_id=self._organization_id,
                    data=data or {},
                )
            )
            logger.debug(f"Emitted TTS state event: {state.value}")
        except Exception as error:
            logger.error(
                "TTS state event emission failed state=%s error_type=%s",
                state.value,
                type(error).__name__,
            )

    def _notify_playback_started(self) -> None:
        if not self._on_playback_started:
            return
        try:
            self._on_playback_started()
        except Exception:
            logger.debug("Playback-start callback failed")

    def _notify_playback_finished(self) -> None:
        if not self._on_playback_finished:
            return
        try:
            self._on_playback_finished()
        except Exception:
            logger.debug("Playback-finished callback failed")

    def set_turn_outcome_callback(
        self,
        callback: Callable[[str | None, VoiceSpeechOutcome], None],
    ) -> None:
        """Bind session-local speech outcome capture after pipeline creation."""
        self._on_turn_outcome = callback

    def set_playback_callbacks(
        self,
        *,
        started: Callable[[], None] | None,
        finished: Callable[[], None] | None,
    ) -> None:
        """Bind transport-local activity tracking after session registration.

        Telephony creates the provider runtime before its WebSocket session is
        registered. Binding here keeps that construction order without making
        the provider adapter aware of conversation activity policy.
        """
        self._on_playback_started = started
        self._on_playback_finished = finished

    def _notify_turn_outcome(
        self,
        request_id: str | None,
        outcome: VoiceSpeechOutcome,
    ) -> None:
        if self._on_turn_outcome is None:
            return
        try:
            self._on_turn_outcome(request_id, outcome)
        except Exception:
            logger.debug("Turn-outcome callback failed")

    def _reset_playback_tracking(self) -> None:
        self._playback_done.clear()
        self._playback_error = None
        self._awaiting_playback_completion = False
        self._received_audio_for_turn = False
        self._sent_text_for_turn = False
        self._last_audio_chunk_at = 0.0
        self._first_text_sent_at = None

    def _service_reports_turn_complete(self) -> bool:
        """Whether the vendor has signalled end-of-turn.

        A plain read: `TTSVendorAdapter.is_turn_complete` is part of the
        contract and defaults to False for vendors with no turn boundary. This
        used to be a `getattr` with a `callable()` branch, because the contract
        did not name the attribute and the code could not assume its shape —
        all four implementations were properties, so that branch was never
        taken.
        """
        return bool(getattr(self._tts_factory.service, "is_turn_complete", False))

    def _service_completion_error(self) -> Exception | None:
        error = getattr(self._tts_factory.service, "turn_completion_error", None)
        if callable(error):
            return error()
        if isinstance(error, Exception):
            return error
        return None

    def _mark_playback_done(
        self,
        *,
        notify_finished: bool = True,
        outcome: VoiceSpeechOutcome = VoiceSpeechOutcome.DRAINED,
    ) -> None:
        request_id = self._active_request_id or self._queued_request_id
        self._awaiting_playback_completion = False
        self._received_audio_for_turn = False
        self._last_audio_chunk_at = 0.0
        self._active_turn_id = None
        self._queued_turn_id = None
        self._active_request_id = None
        self._queued_request_id = None
        self._text_buffer.reset()
        self._playback_done.set()
        self._notify_turn_outcome(request_id, outcome)
        if notify_finished:
            self._notify_playback_finished()

    def _mark_playback_failed(self, error: Exception) -> None:
        self._playback_error = error
        self._mark_playback_done(outcome=VoiceSpeechOutcome.FAILED)

    def is_playback_active(self, grace_seconds: float | None = None) -> bool:
        """Return True while speech is still being produced or draining downstream."""
        if self._active_turn_id is not None or self._queued_turn_id is not None:
            return True
        if self._awaiting_playback_completion or not self._playback_done.is_set():
            return True
        if (
            not self._request_queue.empty()
            or not self._response_queue.empty()
            or not self._consumer_queue.empty()
        ):
            return True

        activity_grace = (
            self._PLAYBACK_ACTIVITY_GRACE_SECONDS
            if grace_seconds is None
            else grace_seconds
        )
        if (
            self._last_playback_activity_at > 0
            and time.monotonic() - self._last_playback_activity_at < activity_grace
        ):
            return True
        return False

    def _maybe_mark_playback_done(self) -> None:
        if not self._awaiting_playback_completion:
            return
        if (
            not self._request_queue.empty()
            or not self._response_queue.empty()
            or not self._consumer_queue.empty()
        ):
            return
        error = self._service_completion_error()
        if error is not None:
            if isinstance(error, TTSConnectionClosed):
                self._mark_playback_failed(TTSConnectionFailed("TTS playback failed."))
                self._is_connected = False
                raise error
            self._mark_playback_failed(error)
            return
        if self._service_reports_turn_complete():
            self._mark_playback_done()

    async def add_to_request_queue(self, tts_item: str | dict):
        """Add text data to the request queue for processing.
        Drops data if the queue is full to prevent blocking or exceptions.
        """
        if isinstance(tts_item, dict) and tts_item.get("type") == "text":
            turn_id = tts_item.get("turn_id")
            request_id = tts_item.get("request_id")
            if turn_id and turn_id != self._queued_turn_id:
                self._queued_turn_id = turn_id
                self._queued_request_id = request_id
                self._playback_done.clear()
                self._notify_playback_started()
        try:
            self._request_queue.put_nowait(tts_item)
        except asyncio.QueueFull:
            self._metrics["request_drops"] += 1
            logger.warning(
                "TTS request queue full size=%s organization_id=%s total_drops=%s",
                self._MAX_QUEUE_SIZE,
                self._organization_id,
                self._metrics["request_drops"],
            )

    async def _read_from_response_queue(self):
        """Get the processed response from the response queue."""
        return await self._response_queue.get()

    async def initialize(self) -> None:
        """Run TTS and surface every fatal startup/runtime failure to the client."""
        try:
            await self._run()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._mark_playback_failed(error)
            self._emit_tts_state(
                state=TTSState.ERROR,
                message="TTS service failed",
                data={"error_type": type(error).__name__},
            )
            logger.error(
                "TTS service terminated error_type=%s",
                type(error).__name__,
            )
            raise

    async def _run(self) -> None:  # noqa: C901 - vendor lifecycle orchestration
        # Emit connecting state
        self._emit_tts_state(
            state=TTSState.CONNECTING,
            message="Connecting to TTS service",
        )

        async with self._tts_factory.connection():
            self._is_connected = True

            # Emit connected state
            self._emit_tts_state(
                state=TTSState.CONNECTED,
                message="TTS service connected",
            )

            async def _keepalive_loop():
                """Send periodic keepalive messages to maintain the connection."""
                try:
                    while self._is_connected:
                        await asyncio.sleep(self._KEEPALIVE_INTERVAL)
                        await self._tts_factory.service.keepalive()
                except asyncio.CancelledError:
                    # Allow cancellation to propagate for clean shutdown
                    raise
                except Exception as error:
                    logger.error(
                        "TTS keepalive loop failed error_type=%s",
                        type(error).__name__,
                    )
                    raise  # Re-raise to trigger task restart

            async def _forward_request():
                """Process text data from the request queue and send it to the TTS service."""
                logger.info("TTS forward_request loop started.")
                try:
                    while self._is_connected:
                        try:
                            # Wait for data with a timeout
                            data = await asyncio.wait_for(
                                self._request_queue.get(), self._REQUEST_QUEUE_TIMEOUT
                            )
                            try:
                                if (
                                    isinstance(data, dict)
                                    and data.get("type") == "text"
                                ):
                                    turn_id = data.get("turn_id")
                                    request_id = data.get("request_id")
                                    text = data.get("text")

                                    # First text in a stream: set the active turn id without interrupting.
                                    if turn_id and self._active_turn_id is None:
                                        self._active_turn_id = turn_id
                                        self._active_request_id = request_id
                                        self._text_buffer.reset()
                                        self._reset_playback_tracking()
                                    elif turn_id and turn_id != self._active_turn_id:
                                        await self.interrupt()
                                        self._active_turn_id = turn_id
                                        self._active_request_id = request_id
                                        self._text_buffer.reset()
                                        self._reset_playback_tracking()

                                    if isinstance(text, str) and text:
                                        for chunk in self._text_buffer.add(text):
                                            await self._process_text_chunk(chunk)

                                elif (
                                    isinstance(data, dict)
                                    and data.get("type") == "finalize"
                                ):
                                    turn_id = data.get("turn_id")
                                    if (not turn_id) or (
                                        turn_id == self._active_turn_id
                                    ):
                                        self._awaiting_playback_completion = True
                                        for chunk in self._text_buffer.flush():
                                            await self._process_text_chunk(chunk)
                                        if self._sent_text_for_turn:
                                            logger.debug(
                                                f"[TTS_PIPELINE] request_queue → vendor.flush (turn_id={turn_id})"
                                            )
                                            await self._tts_factory.service.flush()
                                        else:
                                            self._mark_playback_done()

                                elif isinstance(data, str):
                                    # Backwards compatible path (no turn_id)
                                    text = normalize_tts_text(data)
                                    if text and has_speakable_text(text):
                                        await self._process_text_chunk(text)

                                self._metrics["total_requests_processed"] += 1
                                self._metrics["last_activity"] = (
                                    arrow.utcnow().timestamp()
                                )
                            finally:
                                self._request_queue.task_done()
                        except asyncio.TimeoutError:
                            continue
                except asyncio.CancelledError:
                    # Allow cancellation to propagate for clean shutdown
                    raise
                except TTSConnectionClosed:
                    self._is_connected = False
                    raise
                except Exception as error:
                    self._metrics["errors"] += 1
                    logger.error(
                        "TTS request forwarding failed error_type=%s",
                        type(error).__name__,
                    )
                    raise  # Re-raise to trigger task restart

            async def _receive_response():
                """Receive and process responses from the TTS service."""
                logger.info("TTS receive_response loop started.")
                try:
                    while self._is_connected:
                        try:
                            response = await asyncio.wait_for(
                                self._tts_factory.service.receive_audio(),
                                self._REQUEST_QUEUE_TIMEOUT,
                            )
                            if response:
                                audio_chunk = TTSAudioChunk.from_response(
                                    response,
                                    sample_rate=self.output_audio_format.sample_rate,
                                    encoding=self.output_audio_format.encoding,
                                    request_id=self._active_request_id,
                                )
                                self._received_audio_for_turn = True
                                self._last_audio_chunk_at = time.monotonic()
                                self._last_playback_activity_at = (
                                    self._last_audio_chunk_at
                                )
                                if (
                                    self._metrics["first_audio_latency_seconds"] is None
                                    and self._first_text_sent_at is not None
                                ):
                                    self._metrics["first_audio_latency_seconds"] = (
                                        self._last_audio_chunk_at
                                        - self._first_text_sent_at
                                    )
                                self._metrics["audio_chunks"] += 1
                                self._metrics["audio_bytes"] += len(audio_chunk.data)
                                logger.debug(
                                    f"[TTS_PIPELINE] Vendor returned audio: {len(audio_chunk.data)} bytes → response_queue"
                                )
                                self._response_queue.put_nowait(audio_chunk)
                            else:
                                self._maybe_mark_playback_done()
                        except asyncio.QueueFull:
                            self._metrics["response_drops"] += 1
                            logger.warning("Response queue full, dropping data.")
                        except asyncio.TimeoutError:
                            self._maybe_mark_playback_done()
                            continue
                        except TTSConnectionClosed:
                            logger.info(
                                "[TTS_MANAGER] TTS stream finished. Signaling end of stream."
                            )
                            self._mark_playback_done()
                            break  # Exit the loop gracefully
                except asyncio.CancelledError:
                    logger.info("TTS receive_response loop cancelled.")
                    raise
                except Exception as error:
                    self._metrics["errors"] += 1
                    logger.error(
                        "TTS response receive failed error_type=%s",
                        type(error).__name__,
                    )
                    raise

            async def _respond_to_consumer():
                """Send processed responses to the client."""
                logger.info("TTS respond_to_consumer loop started.")
                try:
                    while self._is_connected:
                        try:
                            response = await asyncio.wait_for(
                                self._read_from_response_queue(),
                                self._REQUEST_QUEUE_TIMEOUT,
                            )
                            if response:
                                audio_chunk = (
                                    response
                                    if isinstance(response, TTSAudioChunk)
                                    else TTSAudioChunk.from_response(response)
                                )
                                audio_bytes = audio_chunk.data
                                self._last_playback_activity_at = time.monotonic()
                                logger.debug(
                                    f"[TTS_PIPELINE] response_queue → consumer_queue: {len(audio_bytes)} bytes"
                                )
                                self._consumer_queue.put_nowait(audio_bytes)
                                self._response_queue.task_done()
                                # Non-blocking recording tap
                                if self._on_audio_chunk:
                                    try:
                                        self._on_audio_chunk(audio_bytes)
                                    except Exception:
                                        pass
                        except asyncio.QueueFull:
                            self._metrics["consumer_drops"] += 1
                            logger.warning("Consumer queue full, dropping data.")
                            self._response_queue.task_done()
                        except asyncio.TimeoutError:
                            # Timeout waiting for response - continue
                            continue
                except asyncio.CancelledError:
                    # Allow cancellation to propagate for clean shutdown
                    raise
                except TTSConnectionClosed:
                    self._is_connected = False
                    raise
                except Exception as error:
                    self._metrics["errors"] += 1
                    logger.error(
                        "TTS client response failed error_type=%s",
                        type(error).__name__,
                    )
                    raise  # Re-raise to trigger task restart

            # Dictionary mapping task names to their coroutine functions
            task_definitions = {
                "request": _forward_request,
                "response": _receive_response,
                "client": _respond_to_consumer,
            }
            if callable(getattr(self._tts_factory.service, "keepalive", None)):
                task_definitions["keepalive"] = _keepalive_loop
            active_tasks = {
                name: asyncio.create_task(coro())
                for name, coro in task_definitions.items()
            }

            try:
                # Emit ready state
                self._emit_tts_state(
                    state=TTSState.READY,
                    message="TTS service ready to synthesize speech",
                )
                # Main task monitoring loop
                while self._is_connected:
                    await asyncio.sleep(self._HEALTH_CHECK_INTERVAL)
                    await monitor_long_running_tasks(
                        task_definitions=task_definitions,
                        active_tasks=active_tasks,
                        exceptions_to_ignore={asyncio.CancelledError},
                        exceptions_to_restart={
                            TTSConnectionClosed,
                            TTSConnectionFailed,
                        },
                    )
            except asyncio.CancelledError:
                logger.info("Process TTS main loop was cancelled")
            except Exception as error:
                logger.error(
                    "TTS main loop failed error_type=%s",
                    type(error).__name__,
                )
                raise
            finally:
                # Clean up phase
                logger.info("Shutting down TTS tasks gracefully...")

                # First, mark as disconnected to signal tasks to stop their loops
                self._is_connected = False
                await teardown_queues(
                    [self._request_queue, self._response_queue],
                    join_timeout=self._JOIN_TIMEOUT,
                )
                await teardown_long_running_tasks(active_tasks)
                logger.info("All TTS tasks have been stopped")

    async def interrupt(self):
        """Interrupt the TTS by clearing all queues and flushing the vendor service."""
        logger.info("Interrupting TTS")
        self._metrics["interruptions"] += 1

        # 1. Clear internal queues
        while not self._request_queue.empty():
            try:
                self._request_queue.get_nowait()
                self._request_queue.task_done()
            except asyncio.QueueEmpty:
                break
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
                self._response_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # 2. Drain the consumer-facing queue to discard any buffered audio.
        drained_count = 0
        while not self._consumer_queue.empty():
            try:
                self._consumer_queue.get_nowait()
                self._consumer_queue.task_done()
                drained_count += 1
            except asyncio.QueueEmpty:
                break
        if drained_count > 0:
            logger.info(f"Drained {drained_count} items from the TTS consumer queue.")

        # 3. Propagate interruption to the specific TTS implementation (e.g., Cartesia)
        try:
            await self._tts_factory.service.handle_interruption()
        except Exception:
            self._metrics["errors"] += 1
            raise
        finally:
            self._mark_playback_done(outcome=VoiceSpeechOutcome.INTERRUPTED)
        logger.info("TTS interrupted successfully.")

    async def _process_text_chunk(self, text: str) -> None:
        logger.debug(
            "[TTS_PIPELINE] request_queue → vendor.send_text chars=%d",
            len(text),
        )
        if self._first_text_sent_at is None:
            self._first_text_sent_at = time.monotonic()
        await self._tts_factory.service.send_text(text)
        self._sent_text_for_turn = True

    async def wait_until_done(self, timeout: float = 10.0) -> bool:
        """Wait until TTS playback finishes or timeout expires.

        Args:
            timeout: Maximum seconds to wait for playback to finish.

        Returns:
            True if playback completed, False if timeout expired.

        """
        try:
            await asyncio.wait_for(self._playback_done.wait(), timeout=timeout)
            if self._playback_error is not None:
                logger.warning(
                    "TTS turn ended with error organization_id=%s error_type=%s",
                    self._organization_id,
                    type(self._playback_error).__name__,
                )
                return False
            return True
        except asyncio.TimeoutError:
            logger.warning(
                "TTS wait_until_done timed out timeout_seconds=%s organization_id=%s",
                timeout,
                self._organization_id,
            )
            return False

    async def wait_until_flushed(self, timeout: float = 15.0) -> bool:
        """Wait until synthesis and all downstream audio writes finish."""
        try:
            async with asyncio.timeout(timeout):
                await self._request_queue.join()
                if not await self.wait_until_done(timeout=timeout):
                    return False
                await self._consumer_queue.join()
                return True
        except TimeoutError:
            logger.warning(
                "TTS flush timed out organization_id=%s",
                self._organization_id,
            )
            return False

    async def disconnect(self):
        """Disconnect from the TTS service and clean up resources."""
        if self.is_playback_active():
            self._mark_playback_done(outcome=VoiceSpeechOutcome.CANCELLED)
        if self._is_connected:
            # Emit disconnected state BEFORE actually disconnecting
            # to ensure the WebSocket connection is still active
            self._emit_tts_state(
                state=TTSState.DISCONNECTED,
                message="TTS service disconnected",
            )

            await self._tts_factory.service.disconnect()
            self._is_connected = False

            logger.info("Disconnected from TTS service")
        else:
            logger.warning("TTS service is already disconnected")
