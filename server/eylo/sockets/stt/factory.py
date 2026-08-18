"""Adapter construction for the `stt` socket."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable
from uuid import UUID

from eylo.common.contracts.provider_config import Capability, NotConfiguredError
from eylo.runtime.tasks import monitor_long_running_tasks, teardown_long_running_tasks
from eylo.sockets.stt.adapters.amazon_transcribe_adapter import (
    AmazonTranscribeSTTAdapter,
)
from eylo.sockets.stt.adapters.assemblyai_adapter import AssemblyAIAdapter
from eylo.sockets.stt.adapters.cartesia_adapter import CartesiaAdapter
from eylo.sockets.stt.adapters.deepgram_adapter import DeepgramAdapter
from eylo.sockets.stt.adapters.deepgram_flux_adapter import (
    DeepgramFluxConfig,
    DeepgramFluxSTT,
)
from eylo.sockets.stt.adapters.gladia_adapter import GladiaAdapter
from eylo.sockets.stt.adapters.google_adapter import GoogleAdapter
from eylo.sockets.stt.adapters.revai_adapter import RevAIAdapter
from eylo.sockets.stt.adapters.sarvam_adapter import SarvamSTT, SarvamSTTConfig
from eylo.sockets.stt.adapters.speechmatics_adapter import SpeechmaticsAdapter
from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.exceptions import STTConnectionClosed, STTConnectionFailed
from eylo.sockets.stt.schemas import (
    STTCapabilities,
    STTConfig,
    STTEvent,
    STTMetricsSnapshot,
)

logger = logging.getLogger(__name__)

_KEEPALIVE_INTERVAL = 5

_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "amazon-transcribe": frozenset(
        {"region", "language", "access_key_id", "secret_access_key"}
    ),
    "assemblyai": frozenset({"model", "api_key"}),
    "cartesia": frozenset({"model", "language", "api_key"}),
    "deepgram": frozenset({"model", "language", "api_key"}),
    "deepgram-flux": frozenset({"model", "api_key"}),
    "gladia": frozenset({"language", "api_key"}),
    "google": frozenset({"model", "language", "service_account_json"}),
    "revai": frozenset({"language", "api_key"}),
    "sarvam": frozenset({"model", "language", "api_key"}),
    "speechmatics": frozenset({"language", "api_key"}),
}


class STTFactory:
    """Factory for creating instances of STT services.

    Currently supports:
    - Amazon Transcribe Streaming
    - AssemblyAI
    - Cartesia
    - Deepgram and Deepgram Flux
    - Gladia
    - Google Cloud Speech
    - Rev.AI
    - Sarvam
    - Speechmatics
    """

    def __init__(
        self,
        organization_id: UUID,
        session_id: str,
        consumer_queue: asyncio.Queue | None = None,
        stt_config: STTConfig | dict | None = None,
        stt_vendor: str | None = None,
        *,
        api_key: str | None = None,
    ):
        """Initialize the STT factory.

        Args:
            organization_id: Organization UUID
            session_id: Session ID
            consumer_queue: Queue for responses
            stt_config: Configuration for the STT service
            stt_vendor: STT service provider ("deepgram", "speechmatics", "google", "gladia", "revai", "sarvam")
            api_key: Optional resolved API key. When provided, it overrides any settings-based key.

        """
        self._organization_id = organization_id
        self._session_id = session_id

        self._typed_config = STTConfig.from_mapping(
            stt_config,
            vendor=stt_vendor,
        )
        self._stt_vendor = self._typed_config.vendor
        self._stt_service: STTVendorAdapter | None = None
        self._respond_back_queue = (
            consumer_queue if consumer_queue is not None else asyncio.Queue()
        )
        self._metrics = STTMetricsSnapshot()

        self._stt_config = self._typed_config.to_adapter_config()
        supplied_config = (
            stt_config.to_adapter_config()
            if isinstance(stt_config, STTConfig)
            else dict(stt_config or {})
        )
        if "encoding" not in self._stt_config:
            input_audio_codec = self._stt_config.get("input_audio_codec")
            if input_audio_codec:
                self._stt_config["encoding"] = input_audio_codec
        # Set default configuration for turn-based conversation
        self._stt_config.setdefault("endpointing", 500)
        if "utterance_end_ms" not in self._stt_config:
            self._stt_config["utterance_end_ms"] = 1000
        self._stt_config.setdefault("vad_events", True)
        self._stt_config.setdefault("interim_results", True)
        self._stt_config.setdefault("sample_rate", 16000)
        default_encoding = (
            "pcm_s16le"
            if self._stt_vendor in {"assemblyai", "cartesia"}
            else "linear16"
        )
        if (
            "encoding" not in supplied_config
            and "input_audio_codec" not in supplied_config
        ):
            self._stt_config["encoding"] = default_encoding
        self._stt_config.setdefault("encoding", default_encoding)

        if api_key is not None:
            self._stt_config["api_key"] = api_key
        _require_configuration(self._stt_vendor, self._stt_config)

    @property
    def config(self) -> STTConfig:
        """Get the normalized typed config."""
        return self._typed_config

    @property
    def metrics(self) -> dict[str, Any]:
        """Get current lightweight metrics."""
        return self._metrics.as_dict()

    @property
    def capabilities(self) -> STTCapabilities:
        """Get capabilities advertised by the selected vendor."""
        return _capabilities_for_vendor(self._stt_vendor)

    @property
    def consumer_queue(self) -> asyncio.Queue:
        """Get the response queue."""
        return self._respond_back_queue

    @property
    def service(self) -> STTVendorAdapter:
        """Get the current STT service, initializing if needed."""
        if self._stt_service:
            return self._stt_service
        return self._initialize_agent()

    @property
    def is_connected(self) -> bool:
        """Check if the STT service is connected."""
        return self._get_connection_status()

    def _get_connection_status(self) -> bool:
        """Check if the STT service is connected."""
        return self.service.is_connected

    def _initialize_agent(self) -> STTVendorAdapter:
        """Create an STT service instance based on the vendor."""
        if not self._stt_service:
            if self._stt_vendor == "deepgram":
                self._stt_service = DeepgramAdapter(config=self._stt_config)
            elif self._stt_vendor == "deepgram-flux":
                self._stt_service = DeepgramFluxSTT(
                    config=DeepgramFluxConfig(**self._stt_config)
                )
            elif self._stt_vendor == "speechmatics":
                # Use new voice module Speechmatics via adapter
                self._stt_service = SpeechmaticsAdapter(config=self._stt_config)
            elif self._stt_vendor == "google":
                # Use new voice module Google Cloud Speech via adapter
                self._stt_service = GoogleAdapter(config=self._stt_config)
            elif self._stt_vendor == "gladia":
                # Use new voice module Gladia via adapter
                self._stt_service = GladiaAdapter(config=self._stt_config)
            elif self._stt_vendor == "revai":
                # Use new voice module Rev.AI via adapter
                self._stt_service = RevAIAdapter(config=self._stt_config)
            elif self._stt_vendor == "sarvam":
                self._stt_service = SarvamSTT(
                    config=SarvamSTTConfig(**self._stt_config)
                )
            elif self._stt_vendor == "assemblyai":
                self._stt_service = AssemblyAIAdapter(config=self._stt_config)
            elif self._stt_vendor == "cartesia":
                self._stt_service = CartesiaAdapter(config=self._stt_config)
            elif self._stt_vendor == "amazon-transcribe":
                self._stt_service = AmazonTranscribeSTTAdapter(
                    config=self._stt_config,
                )
            else:
                raise ValueError(f"Unsupported STT vendor: {self._stt_vendor}")
        return self._stt_service

    async def disconnect(self):
        """Disconnect the STT service."""
        if self._stt_service:
            await self._stt_service.disconnect()
            self._stt_service = None

    async def reconnect(self):
        """Reconnect the current STT service instance in place."""
        service = self.service
        try:
            await service.disconnect()
        except Exception as error:
            logger.warning(
                "Ignoring STT disconnect error during reconnect error_type=%s",
                type(error).__name__,
            )

        self._metrics.mark_reconnect()
        ws = await service.connect()
        while not self.is_connected:
            await asyncio.sleep(0.01)
        return ws

    @asynccontextmanager
    async def connection(
        self,
    ) -> AsyncGenerator[object, None]:
        """Establish a connection to the STT service."""
        ws = await self.service.connect()
        self._metrics.mark_connected()
        while not self.is_connected:
            # spin-loop until the connection is established
            await asyncio.sleep(0.01)

        # Dictionary mapping task names to their coroutine functions
        async def _keepalive_loop():
            """Send periodic keepalive messages to maintain the connection."""
            try:
                while self.is_connected:
                    await asyncio.sleep(_KEEPALIVE_INTERVAL)
                    await self.service.keepalive()
            except asyncio.CancelledError:
                # Allow cancellation to propagate for clean shutdown
                raise
            except Exception as error:
                logger.error(
                    "STT keepalive loop failed error_type=%s",
                    type(error).__name__,
                )
                raise  # Re-raise to trigger task restart

        async def _await_response():
            """Receive and process responses from the STT service."""
            try:
                while self.is_connected:
                    try:
                        event = await self.service.receive_event()
                        if event:
                            self._metrics.mark_event(event.type.value)
                            logger.info(
                                "STTFactory received type=%s final=%s "
                                "transcript_chars=%d",
                                event.type.value,
                                event.is_final,
                                len(event.transcript),
                            )
                            try:
                                self._respond_back_queue.put_nowait(event)
                            except asyncio.QueueFull:
                                logger.warning(
                                    "STT response queue is full; dropping new response"
                                )
                        else:
                            await asyncio.sleep(0.01)

                    except asyncio.TimeoutError:
                        # Timeout waiting for response - continue
                        continue
            except asyncio.CancelledError:
                # Allow cancellation to propagate for clean shutdown
                raise
            except Exception as error:
                self._metrics.mark_error()
                logger.error(
                    "STT response loop failed error_type=%s",
                    type(error).__name__,
                )
                raise  # Re-raise to trigger task restart

        async def _monitor_tasks():
            try:
                # Main task monitoring loop
                while self.is_connected:  # this is important to check
                    # otherwise we will go to finally block and cancel all tasks
                    await monitor_long_running_tasks(
                        task_definitions=_long_running_tasks,
                        active_tasks=_active_long_running_tasks,
                        exceptions_to_ignore={asyncio.CancelledError},
                        exceptions_to_restart={STTConnectionFailed},
                    )
                    await asyncio.sleep(_KEEPALIVE_INTERVAL)

            except asyncio.CancelledError:
                pass
            except STTConnectionClosed:
                logger.info("STT connection closed")
            except Exception as error:
                logger.error(
                    "STT task monitor failed error_type=%s",
                    type(error).__name__,
                )
            finally:
                await teardown_long_running_tasks(
                    active_tasks=_active_long_running_tasks,
                )

        _long_running_tasks: dict[str, Callable] = {
            "stt_factory_service_keepalive_loop": _keepalive_loop,
            "stt_factory_service_await_response": _await_response,
        }

        # Initialize active tasks dictionary
        _active_long_running_tasks: dict[str, asyncio.Task] = {}
        monitor_task: asyncio.Task[None] | None = None

        try:
            # Start the monitoring task
            # This task will monitor the long-running tasks and restart them if needed
            for name, coro in _long_running_tasks.items():
                _active_long_running_tasks[name] = asyncio.create_task(coro())
            monitor_task = asyncio.create_task(_monitor_tasks())
            yield ws
        finally:
            # NOTE: in the STT RT we have already called the disconnect method
            await self.disconnect()
            if monitor_task is not None:
                if not monitor_task.done():
                    monitor_task.cancel()
                await asyncio.gather(monitor_task, return_exceptions=True)
            await asyncio.gather(
                *[t for t in _active_long_running_tasks.values() if not t.done()],
                return_exceptions=True,
            )
            await teardown_long_running_tasks(
                active_tasks=_active_long_running_tasks,
            )


def _require_configuration(vendor: str, config: dict[str, Any]) -> None:
    required = _REQUIRED_FIELDS.get(vendor)
    if required is None:
        return
    missing = sorted(
        name
        for name in required
        if not isinstance(config.get(name), str) or not config[name].strip()
    )
    if missing:
        raise NotConfiguredError(
            capability=Capability.STT,
            missing=missing,
            configure_via="/api/stt-configs",
        )


def _capabilities_for_vendor(vendor: str) -> STTCapabilities:
    """Return current best-known capabilities without changing vendor selection."""
    normalized_vendor = vendor.replace("-", "_")
    if normalized_vendor == "deepgram":
        return STTCapabilities(
            vad_events=True,
            interim_results=True,
            word_timestamps=True,
            punctuation=True,
        )
    if normalized_vendor == "deepgram_flux":
        return STTCapabilities(
            turn_detection=True,
            interim_results=True,
            word_timestamps=True,
            punctuation=True,
        )
    if normalized_vendor == "assemblyai":
        return STTCapabilities(
            turn_detection=True,
            interim_results=True,
            speaker_labels=True,
        )
    if normalized_vendor == "google":
        return STTCapabilities(
            interim_results=True,
            word_timestamps=True,
            speaker_labels=True,
            language_detection=True,
            punctuation=True,
            profanity_filter=True,
        )
    if normalized_vendor == "amazon_transcribe":
        return STTCapabilities(
            interim_results=True,
            word_timestamps=True,
            speaker_labels=True,
            custom_vocabulary=True,
            punctuation=True,
        )
    if normalized_vendor in {"gladia", "revai", "speechmatics", "cartesia", "sarvam"}:
        return STTCapabilities(interim_results=True)
    return STTCapabilities()
