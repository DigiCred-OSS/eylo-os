"""Amazon Polly adapter for the TTS socket contract."""

from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import suppress
from typing import Any

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.exceptions import TTSConnectionClosed, TTSConnectionFailed
from eylo.sockets.tts.schemas import TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

_PROVIDER = "amazon-polly"
_PCM_SAMPLE_RATES = (8000, 16000)
_AUDIO_CHUNK_SIZE = 4096
_QUEUE_SIZE = 500


class AmazonPollyTTSAdapter(TTSVendorAdapter):
    """Synthesize ordered text fragments through Amazon Polly.

    Polly uses one HTTP request per fragment and streams the response body. A
    single background worker preserves fragment order while the voice pipeline
    consumes audio concurrently. Interruption cancels the active response and
    discards all queued text/audio for the interrupted generation.
    """

    def __init__(self, config: TTSConfig) -> None:
        contract = config.model_copy(
            update={
                "sample_rate": _polly_sample_rate(config.sample_rate),
                "encoding": "pcm_s16le",
            }
        )
        super().__init__(contract)
        options = contract.options
        self._region = _required_option(options, "region")
        self._engine = _required_string(contract.model, "model")
        self._voice = _required_string(contract.voice, "voice")
        self._language = _required_string(contract.language, "language")
        self._sample_rate = contract.sample_rate

        self._session = aioboto3.Session(
            aws_access_key_id=_required_option(options, "access_key_id"),
            aws_secret_access_key=_required_option(
                options,
                "secret_access_key",
            ),
            aws_session_token=_optional_option(options, "session_token"),
            region_name=self._region,
        )
        self._client_context: Any = None
        self._client: Any = None
        self._text_queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue(
            maxsize=_QUEUE_SIZE
        )
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_SIZE)
        self._worker_task: asyncio.Task[None] | None = None
        self._connected = False
        self._synthesizing = False
        self._flush_requested = False
        self._turn_complete = False
        self._generation = 0
        self._completion_error: Exception | None = None

    async def connect(self) -> object:
        if self._connected and self._client is not None:
            return self

        self._client_context = self._session.client("polly")
        try:
            self._client = await self._client_context.__aenter__()
            await self._verify_connection()
        except TTSConnectionFailed:
            await self._close_client()
            raise
        except Exception as error:
            await self._close_client()
            logger.error(
                "Amazon Polly connection failed error_type=%s",
                type(error).__name__,
            )
            raise TTSConnectionFailed("Amazon Polly request failed.") from None

        self._connected = True
        self._completion_error = None
        self._worker_task = asyncio.create_task(self._synthesis_loop())
        logger.info(
            "Amazon Polly connected region=%s engine=%s voice=%s sample_rate=%s",
            self._region,
            self._engine,
            self._voice,
            self._sample_rate,
        )
        return self

    async def disconnect(self) -> None:
        self._connected = False
        await self._stop_worker()
        self._drain_queue(self._text_queue)
        self._drain_queue(self._audio_queue)
        await self._close_client()
        self._turn_complete = True
        logger.info("Amazon Polly disconnected")

    async def send_text(self, text: str) -> None:
        if not self._connected or self._client is None:
            raise TTSConnectionClosed("Amazon Polly is not connected.")
        if not text or not text.strip():
            return
        self._completion_error = None
        self._flush_requested = False
        self._turn_complete = False
        await self._text_queue.put((self._generation, text))

    async def receive_audio(self) -> bytes | None:
        try:
            chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            self._update_turn_complete()
            return None
        self._audio_queue.task_done()
        self._update_turn_complete()
        return chunk

    async def handle_interruption(self) -> None:
        self._generation += 1
        await self._stop_worker()
        self._drain_queue(self._text_queue)
        self._drain_queue(self._audio_queue)
        self._synthesizing = False
        self._flush_requested = True
        self._completion_error = None
        self._turn_complete = True
        if self._connected:
            self._worker_task = asyncio.create_task(self._synthesis_loop())

    async def flush(self) -> None:
        self._flush_requested = True
        self._update_turn_complete()

    async def keepalive(self) -> None:
        """Polly uses request/response HTTP and needs no keepalive frame."""

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_turn_complete(self) -> bool:
        self._update_turn_complete()
        return self._turn_complete

    @property
    def turn_completion_error(self) -> Exception | None:
        return self._completion_error

    @property
    def provider(self) -> str:
        return _PROVIDER

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def model(self) -> str:
        return self._engine

    @property
    def capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            streaming=True,
            batch_synthesize=True,
            native_interruption=False,
            aligned_transcript=False,
            emotion_control=False,
            speed_control=False,
            voice_cloning=False,
            context_continuity=False,
            word_timestamps=False,
            sample_rates=_PCM_SAMPLE_RATES,
            languages_count=1,
        )

    async def _verify_connection(self) -> None:
        response = await self._synthesize(".")
        audio_stream = response.get("AudioStream")
        if audio_stream is None:
            raise TTSConnectionFailed(
                "Amazon Polly verification returned no audio stream."
            )
        try:
            while await audio_stream.read(_AUDIO_CHUNK_SIZE):
                pass
        finally:
            await _close_audio_stream(audio_stream)

    async def _synthesis_loop(self) -> None:
        while True:
            generation, text = await self._text_queue.get()
            try:
                if generation != self._generation:
                    continue
                self._synthesizing = True
                await self._synthesize_and_queue(text, generation)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._completion_error = _connection_error(error)
                logger.error(
                    "Amazon Polly synthesis failed error_type=%s",
                    type(error).__name__,
                )
            finally:
                self._synthesizing = False
                self._text_queue.task_done()
                self._update_turn_complete()

    async def _synthesize_and_queue(self, text: str, generation: int) -> None:
        response = await self._synthesize(text)
        audio_stream = response.get("AudioStream")
        if audio_stream is None:
            raise TTSConnectionFailed("Amazon Polly returned no audio stream.")
        try:
            while self._connected and generation == self._generation:
                chunk = await audio_stream.read(_AUDIO_CHUNK_SIZE)
                if not chunk:
                    break
                await self._audio_queue.put(bytes(chunk))
        finally:
            await _close_audio_stream(audio_stream)

    async def _synthesize(self, text: str) -> dict[str, Any]:
        if self._client is None:
            raise TTSConnectionClosed("Amazon Polly is not connected.")
        try:
            return await self._client.synthesize_speech(
                Engine=self._engine,
                LanguageCode=self._language,
                OutputFormat="pcm",
                SampleRate=str(self._sample_rate),
                Text=text,
                TextType="text",
                VoiceId=self._voice,
            )
        except (BotoCoreError, ClientError) as error:
            raise _connection_error(error) from None

    async def _stop_worker(self) -> None:
        task = self._worker_task
        self._worker_task = None
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _close_client(self) -> None:
        context = self._client_context
        self._client_context = None
        self._client = None
        if context is not None:
            with suppress(Exception):
                await context.__aexit__(None, None, None)

    def _update_turn_complete(self) -> None:
        self._turn_complete = bool(
            self._flush_requested
            and not self._synthesizing
            and self._text_queue.empty()
            and self._audio_queue.empty()
        )

    @staticmethod
    def _drain_queue(queue: asyncio.Queue[Any]) -> None:
        while not queue.empty():
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                return


def _required_option(options: dict[str, Any], field_name: str) -> str:
    return _required_string(options.get(field_name), field_name)


def _optional_option(options: dict[str, Any], field_name: str) -> str | None:
    value = options.get(field_name)
    if value is None:
        return None
    return _required_string(value, field_name)


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Amazon Polly requires {field_name}.")
    return value.strip()


def _polly_sample_rate(value: int) -> int:
    if value not in _PCM_SAMPLE_RATES:
        raise ValueError("Amazon Polly PCM sample_rate must be 8000 or 16000.")
    return value


def _connection_error(error: Exception) -> TTSConnectionFailed:
    if isinstance(error, TTSConnectionFailed):
        return error
    return TTSConnectionFailed("Amazon Polly request failed.")


async def _close_audio_stream(audio_stream: Any) -> None:
    close = getattr(audio_stream, "close", None)
    if not callable(close):
        return
    with suppress(Exception):
        result = close()
        if inspect.isawaitable(result):
            await result
