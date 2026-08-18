"""OpenAI implementation of the provider-neutral TTS contract."""

import asyncio
import logging
from typing import Optional

import aiohttp

from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.exceptions import TTSConnectionClosed, TTSConnectionFailed
from eylo.sockets.tts.schemas import TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

_DEFAULT_SPEED = 1.0
_DEFAULT_SAMPLE_RATE = 24000
_CHUNK_SIZE = 4096  # bytes per chunk pushed to response queue
_MAX_CONSECUTIVE_ERRORS = 3


class OpenAITTSConfig:
    """Configuration for OpenAI TTS adapter."""

    def __init__(
        self,
        *,
        model: str,
        voice: str,
        speed: float = _DEFAULT_SPEED,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        **kwargs,  # Accept extra keys from tts_config without breaking
    ):
        self.model = model
        self.voice = voice
        self.speed = speed
        self.api_key = api_key
        self.base_url = base_url

        if not self.api_key:
            raise ValueError("OpenAI TTS api_key is required.")


class OpenAITTSAdapter(TTSVendorAdapter):
    """Adapter bridging OpenAI HTTP TTS to the streaming TTS manager interface.

    Validates connectivity on connect() so the manager only emits
    TTS_CONNECTED/TTS_READY when the API is actually reachable.
    Tracks consecutive synthesis failures and raises TTSConnectionClosed
    after repeated errors, allowing the manager to trigger disconnect/drop.
    """

    def __init__(self, config: OpenAITTSConfig):
        # Feed the contract config up from the vendor config. getattr with
        # fallbacks because vendor configs disagree — deepgram has no voice,
        # murf calls it voice_id, openai carries no sample_rate. Unset keys
        # are omitted: passing None would override a field default with an
        # invalid value.
        _contract = {
            "model": getattr(config, "model", None),
            "voice": getattr(config, "voice", None)
            or getattr(config, "voice_id", None),
            "sample_rate": _DEFAULT_SAMPLE_RATE,
            "encoding": "pcm_s16le",
        }
        super().__init__(
            TTSConfig(
                vendor="openai",
                **{k: v for k, v in _contract.items() if v is not None},
            )
        )
        self._config = config
        self._response_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._session = None  # aiohttp.ClientSession
        self._connected = False
        self._active_task: Optional[asyncio.Task] = None
        self._active_tasks: set[asyncio.Task] = set()
        self._completion_error: Exception | None = None
        self._consecutive_errors = 0

    async def connect(self):
        """Initialize HTTP session and validate API reachability.

        Makes a minimal synthesis call ("test") to verify:
        - API key is valid
        - Network is reachable
        - Model/voice combination works

        Raises TTSConnectionFailed if validation fails — same behavior as
        WebSocket vendors, so the manager won't emit CONNECTED/READY.
        """
        self._session = aiohttp.ClientSession()

        # Validate connectivity with a minimal synthesis request
        try:
            payload = {
                "model": self._config.model,
                "input": ".",
                "voice": self._config.voice,
                "response_format": "pcm",
            }
            async with self._session.post(
                f"{self._config.base_url}/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise TTSConnectionFailed(
                        "OpenAI TTS: Invalid API key (401 Unauthorized)"
                    )
                if resp.status == 429:
                    raise TTSConnectionFailed(
                        "OpenAI TTS: Rate limited (429). Cannot establish connection."
                    )
                if resp.status >= 500:
                    raise TTSConnectionFailed(
                        f"OpenAI TTS: Server error ({resp.status}). Service unavailable."
                    )
                if resp.status != 200:
                    await resp.read()
                    raise TTSConnectionFailed(
                        f"OpenAI TTS: Validation failed ({resp.status})."
                    )
                # Drain the validation response (small audio for ".")
                async for _ in resp.content.iter_chunked(_CHUNK_SIZE):
                    pass

        except TTSConnectionFailed:
            await self._session.close()
            self._session = None
            raise
        except asyncio.TimeoutError:
            await self._session.close()
            self._session = None
            raise TTSConnectionFailed(
                "OpenAI TTS: Connection timed out. API unreachable."
            )
        except Exception as error:
            await self._session.close()
            self._session = None
            raise TTSConnectionFailed(
                "OpenAI TTS: Connection validation failed."
            ) from error

        self._connected = True
        self._consecutive_errors = 0
        logger.info(
            "OpenAI TTS adapter connected (model=%s, voice=%s)",
            self._config.model,
            self._config.voice,
        )
        return self

    async def disconnect(self):
        """Close HTTP session and cancel pending work."""
        self._connected = False

        await self._cancel_active_tasks()

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("OpenAI TTS adapter disconnected")

    async def send_text(self, text: str) -> None:
        """Synthesize text via HTTP and push audio chunks to response queue.

        Args:
            text: Text to synthesize (max 4096 chars per OpenAI docs).

        Raises:
            TTSConnectionClosed: After MAX_CONSECUTIVE_ERRORS failures,
                signaling the manager to tear down the pipeline.

        """
        if not self._connected or not self._session:
            raise TTSConnectionClosed("Not connected. Call connect() first.")
        if not text or not text.strip():
            return

        # Run synthesis in background task so manager loop isn't blocked
        if not self._active_tasks:
            self._completion_error = None
        task = asyncio.create_task(self._synthesize_and_queue(text))
        self._active_task = task
        self._active_tasks.add(task)
        task.add_done_callback(self._track_task_completion)

    async def _synthesize_and_queue(self, text: str):
        """Make HTTP call and chunk audio into response queue.

        Tracks consecutive errors. After _MAX_CONSECUTIVE_ERRORS failures,
        raises TTSConnectionClosed so the manager's _forward_request loop
        re-raises and triggers the disconnect/teardown flow.
        """
        try:
            payload = {
                "model": self._config.model,
                "input": text,
                "voice": self._config.voice,
                "speed": self._config.speed,
                "response_format": "pcm",
            }

            async with self._session.post(
                f"{self._config.base_url}/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    await resp.read()
                    logger.error(
                        "OpenAI TTS HTTP failure status=%d",
                        resp.status,
                    )
                    self._consecutive_errors += 1
                    if self._consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                        raise TTSConnectionClosed(
                            f"OpenAI TTS: {self._consecutive_errors} consecutive "
                            f"failures (last: HTTP {resp.status}). Treating as disconnected."
                        )
                    raise TTSConnectionFailed(
                        f"OpenAI TTS request failed with HTTP {resp.status}."
                    )

                # Success — reset error counter
                self._consecutive_errors = 0

                # Stream response body in chunks
                async for chunk in resp.content.iter_chunked(_CHUNK_SIZE):
                    if not self._connected:
                        break
                    try:
                        self._response_queue.put_nowait(chunk)
                    except asyncio.QueueFull:
                        logger.warning("OpenAI TTS response queue full, dropping chunk")

        except TTSConnectionClosed:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "OpenAI TTS synthesis failed error_type=%s",
                type(error).__name__,
            )
            self._consecutive_errors += 1
            if self._consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                raise TTSConnectionClosed(
                    f"OpenAI TTS: {self._consecutive_errors} consecutive errors. "
                    f"Last type: {type(error).__name__}."
                )

    async def receive_audio(self) -> Optional[bytes]:
        """Get next audio chunk from the queue.

        Returns:
            Audio bytes (PCM 24kHz 16-bit mono) or None if queue empty.

        """
        try:
            chunk = await asyncio.wait_for(self._response_queue.get(), timeout=0.1)
            return chunk
        except asyncio.TimeoutError:
            return None

    async def flush(self) -> None:
        """No-op for OpenAI TTS — HTTP requests are atomic."""
        pass

    @property
    def is_turn_complete(self) -> bool:
        return bool(
            self._completion_error is None
            and all(task.done() for task in self._active_tasks)
            and self._response_queue.empty()
        )

    @property
    def turn_completion_error(self) -> Exception | None:
        return self._completion_error

    async def _cancel_active_tasks(self) -> None:
        tasks = [task for task in self._active_tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active_tasks.clear()
        self._active_task = None
        self._completion_error = None

    def _track_task_completion(self, task: asyncio.Task) -> None:
        self._active_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and self._completion_error is None:
            self._completion_error = error

    async def handle_interruption(self):
        """Cancel active synthesis and clear buffered audio."""
        await self._cancel_active_tasks()

        # Drain response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @property
    def sample_rate(self) -> int:
        """OpenAI TTS PCM output is 24kHz."""
        return _DEFAULT_SAMPLE_RATE

    @property
    def provider(self) -> str:
        return "openai"

    async def keepalive(self) -> None:
        """HTTP request/response — no socket to keep warm. Explicit no-op."""
        return None

    @property
    def is_connected(self) -> bool:
        return bool(getattr(self, "_connected", False))

    @property
    def model(self) -> str:
        return str(getattr(self._config, "model", "") or "")

    @property
    def capabilities(self) -> TTSCapabilities:
        """Derived from this adapter's own behaviour, not from memory.

        Confirm a False against vendor documentation before relying on it —
        under-claiming makes a caller skip a feature, over-claiming breaks it.
        """
        return TTSCapabilities(
            streaming=True,
            batch_synthesize=False,
            native_interruption=False,
            aligned_transcript=False,
            emotion_control=False,
            speed_control=True,
            voice_cloning=False,
            context_continuity=False,
        )
