"""Amazon Transcribe streaming adapter for the STT socket contract."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aws_sdk_transcribe_streaming.client import TranscribeStreamingClient
from aws_sdk_transcribe_streaming.config import Config
from aws_sdk_transcribe_streaming.models import (
    AudioEvent,
    AudioStreamAudioEvent,
    LanguageCode,
    MediaEncoding,
    PartialResultsStability,
    StartStreamTranscriptionInput,
    TranscriptResultStreamTranscriptEvent,
)
from smithy_aws_core.identity import StaticCredentialsResolver

from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.exceptions import STTConnectionClosed, STTConnectionFailed
from eylo.sockets.stt.schemas import (
    STTCapabilities,
    STTEvent,
    STTEventType,
    TimedWord,
)

logger = logging.getLogger(__name__)

_PROVIDER = "amazon-transcribe"
_SUPPORTED_SAMPLE_RATES = (8000, 16000, 44100, 48000)
_RESPONSE_QUEUE_SIZE = 1000


class AmazonTranscribeSTTAdapter(STTVendorAdapter):
    """Stream signed PCM audio through Amazon Transcribe.

    The adapter receives credentials as resolved primitives. It never reads
    provider configuration, environment credentials, or platform domain types.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._region = _required_string(config, "region")
        self._language = _language_code(config)
        self._sample_rate = _sample_rate(config)
        self._vocabulary_name = _optional_string(config, "vocabulary_name")
        self._language_model_name = _optional_string(
            config,
            "language_model_name",
        )
        self._show_speaker_label = bool(config.get("show_speaker_label", False))
        self._partial_results_stability = _partial_results_stability(config)

        self._client = TranscribeStreamingClient(
            Config(
                region=self._region,
                aws_access_key_id=_required_string(config, "access_key_id"),
                aws_credentials_identity_resolver=StaticCredentialsResolver(),
                aws_secret_access_key=_required_string(
                    config,
                    "secret_access_key",
                ),
                aws_session_token=_optional_string(config, "session_token"),
            )
        )
        self._stream: Any = None
        self._output_stream: Any = None
        self._receive_task: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[STTEvent] = asyncio.Queue(
            maxsize=_RESPONSE_QUEUE_SIZE
        )
        self._connected = False
        self._disconnecting = False
        self._stream_error: Exception | None = None

    async def connect(self) -> object:
        if self._connected and self._stream is not None:
            return self

        request = StartStreamTranscriptionInput(
            language_code=self._language,
            media_sample_rate_hertz=self._sample_rate,
            media_encoding=MediaEncoding.PCM,
            vocabulary_name=self._vocabulary_name,
            show_speaker_label=self._show_speaker_label,
            enable_partial_results_stabilization=(
                self._partial_results_stability is not None
            ),
            partial_results_stability=self._partial_results_stability,
            language_model_name=self._language_model_name,
        )
        try:
            self._stream = await self._client.start_stream_transcription(request)
            _, self._output_stream = await self._stream.await_output()
        except Exception as error:
            self._stream = None
            self._output_stream = None
            raise STTConnectionFailed(
                "Amazon Transcribe connection failed."
            ) from error

        self._disconnecting = False
        self._stream_error = None
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_events())
        logger.info(
            "Amazon Transcribe connected region=%s language=%s sample_rate=%s",
            self._region,
            self._language.value,
            self._sample_rate,
        )
        return self

    async def disconnect(self) -> None:
        self._disconnecting = True
        self._connected = False

        task = self._receive_task
        self._receive_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        stream = self._stream
        self._stream = None
        self._output_stream = None
        if stream is not None:
            try:
                await stream.close()
            except Exception as error:
                logger.warning(
                    "Amazon Transcribe stream close failed error_type=%s",
                    type(error).__name__,
                )
        logger.info("Amazon Transcribe disconnected")

    async def send_audio(self, audio_data: bytes) -> None:
        if not self._connected or self._stream is None:
            raise STTConnectionClosed("Amazon Transcribe is not connected.")
        if not audio_data:
            return
        try:
            await self._stream.input_stream.send(
                AudioStreamAudioEvent(value=AudioEvent(audio_chunk=audio_data))
            )
        except Exception as error:
            self._connected = False
            raise STTConnectionClosed(
                "Amazon Transcribe audio stream closed."
            ) from error

    async def receive_event(self, timeout_ms: int = 100) -> STTEvent | None:
        if self._stream_error is not None:
            error = self._stream_error
            self._stream_error = None
            raise STTConnectionFailed(
                "Amazon Transcribe response stream failed."
            ) from error
        try:
            return await asyncio.wait_for(
                self._events.get(),
                timeout=timeout_ms / 1000,
            )
        except asyncio.TimeoutError:
            return None

    async def keepalive(self) -> None:
        """Amazon Transcribe has no separate keepalive frame."""

    async def flush(self) -> None:
        """Amazon Transcribe exposes final results through continuous audio."""

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def provider(self) -> str:
        return _PROVIDER

    @property
    def model(self) -> str:
        return self._language_model_name or "standard"

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def capabilities(self) -> STTCapabilities:
        return STTCapabilities(
            streaming=True,
            batch_recognize=False,
            interim_results=True,
            vad_events=False,
            turn_detection=False,
            word_timestamps=True,
            speaker_labels=True,
            language_detection=False,
            custom_vocabulary=True,
            punctuation=True,
            supported_encodings=("pcm_s16le", "linear16"),
            supported_sample_rates=_SUPPORTED_SAMPLE_RATES,
        )

    async def _receive_events(self) -> None:
        try:
            while self._connected and self._output_stream is not None:
                event = await self._output_stream.receive()
                if not isinstance(event, TranscriptResultStreamTranscriptEvent):
                    raise STTConnectionFailed(
                        "Amazon Transcribe returned a stream error."
                    )
                await self._enqueue_transcript_event(event)
        except StopAsyncIteration:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self._disconnecting:
                self._stream_error = error
                logger.error(
                    "Amazon Transcribe receive failed error_type=%s",
                    type(error).__name__,
                )
        finally:
            if not self._disconnecting:
                self._connected = False

    async def _enqueue_transcript_event(
        self,
        event: TranscriptResultStreamTranscriptEvent,
    ) -> None:
        transcript = event.value.transcript
        if transcript is None:
            return
        for result in transcript.results or ():
            alternatives = result.alternatives or ()
            if not alternatives:
                continue
            alternative = alternatives[0]
            text = alternative.transcript or ""
            if not text:
                continue
            items = alternative.items or ()
            confidences = [
                item.confidence for item in items if item.confidence is not None
            ]
            confidence = (
                sum(confidences) / len(confidences) if confidences else None
            )
            language = result.language_code
            speaker = next(
                (item.speaker for item in items if item.speaker is not None),
                None,
            )
            words = tuple(
                TimedWord(
                    word=item.content or "",
                    start_time=item.start_time,
                    end_time=item.end_time,
                    confidence=item.confidence or 0.0,
                )
                for item in items
                if item.content
            )
            await self._events.put(
                STTEvent(
                    type=(
                        STTEventType.TRANSCRIPT_PARTIAL
                        if result.is_partial
                        else STTEventType.TRANSCRIPT_FINAL
                    ),
                    provider=self.provider,
                    model=self.model,
                    transcript=text,
                    is_final=not result.is_partial,
                    confidence=confidence,
                    language=language.value if language is not None else None,
                    provider_request_id=result.result_id,
                    words=words,
                    speaker_id=speaker,
                    audio_start_ms=int(result.start_time * 1000),
                    audio_end_ms=int(result.end_time * 1000),
                )
            )


def _required_string(config: dict[str, Any], field_name: str) -> str:
    value = config.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Amazon Transcribe requires {field_name}.")
    return value.strip()


def _optional_string(config: dict[str, Any], field_name: str) -> str | None:
    value = config.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Amazon Transcribe {field_name} must be non-empty.")
    return value.strip()


def _language_code(config: dict[str, Any]) -> LanguageCode:
    value = _required_string(config, "language")
    try:
        return LanguageCode(value)
    except ValueError:
        raise ValueError(
            "Amazon Transcribe language is not supported by the installed SDK."
        ) from None


def _sample_rate(config: dict[str, Any]) -> int:
    value = config.get("sample_rate", 16000)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Amazon Transcribe sample_rate must be an integer.")
    if value not in _SUPPORTED_SAMPLE_RATES:
        raise ValueError("Amazon Transcribe sample_rate is not supported.")
    return value


def _partial_results_stability(
    config: dict[str, Any],
) -> PartialResultsStability | None:
    value = config.get("partial_results_stability")
    if value is None:
        return None
    try:
        return PartialResultsStability(str(value))
    except ValueError:
        raise ValueError(
            "Amazon Transcribe partial_results_stability is invalid."
        ) from None
