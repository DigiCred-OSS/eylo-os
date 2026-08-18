"""ElevenLabs implementation of the provider-neutral TTS contract."""

from __future__ import annotations

import json
import logging
from typing import Any

from eylo.common.contracts.provider_config import NotConfiguredError
from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.schemas import RetryOptions, TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

PROVIDER = "elevenlabs"

# ElevenLabs streams PCM at the rate named in `output_format`. 16 kHz matches
# what the voice pipeline resamples against; it is a transport fact rather than
# a vendor preference, so it is not operator configuration.
OUTPUT_FORMAT = "pcm_16000"
SAMPLE_RATE = 16000


# ElevenLabs-specific keys read from `TTSConfig.options`. The canonical config
# carries what every vendor has — voice, model, language, sample rate — and
# `options` carries what only this one has. That split is what makes a single
# interface possible without flattening vendors into a lowest common
# denominator.
_VOICE_SETTING_KEYS = (
    "stability",
    "similarity_boost",
    "style",
    "use_speaker_boost",
    "speed",
)


class ElevenLabsTTSAdapter(TTSVendorAdapter):
    """ElevenLabs websocket TTS, contract-first."""

    def __init__(
        self,
        config: TTSConfig,
        retry_options: RetryOptions | None = None,
    ) -> None:
        contract = config.model_copy(
            update={"sample_rate": SAMPLE_RATE, "encoding": "pcm_s16le"}
        )
        super().__init__(contract, retry_options)
        self._ws: Any = None
        self._turn_complete = False

        self._api_key = str(contract.options.get("api_key") or "")
        if not self._api_key:
            raise NotConfiguredError(
                missing=("api_key",),
                capability="tts",
                configure_via="/api/tts-configs",
            )
        # Required by the vendor, and the one field that must never be
        # defaulted: a voice is what the caller's users actually hear.
        if not contract.voice:
            raise NotConfiguredError(
                missing=("voice",),
                capability="tts",
                configure_via="/api/tts-configs",
            )

    @property
    def config(self) -> TTSConfig:
        return self._contract_config

    def voice_settings(self) -> dict[str, Any]:
        """Only what the operator set. Absent keys let the vendor decide."""
        options = self.config.options
        return {
            key: options[key]
            for key in _VOICE_SETTING_KEYS
            if options.get(key) is not None
        }

    def query_params(self) -> dict[str, str]:
        params = {"output_format": OUTPUT_FORMAT}
        # Omitted when unset so ElevenLabs applies its own default, and keeps
        # applying it when they change it.
        if self.config.model:
            params["model_id"] = str(self.config.model)
        if self.config.language:
            params["language_code"] = str(self.config.language)
        return params

    # ---- identity ----------------------------------------------------

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def model(self) -> str:
        # Empty string, not an invented name: unset means the vendor is
        # choosing, and claiming a model we did not send would be a lie in
        # whatever reports this.
        return str(self.config.model or "")

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def capabilities(self) -> TTSCapabilities:
        """What this vendor can do on this path, stated rather than discovered.

        `native_interruption` is false because the websocket has no cancel
        message — interruption is handled by dropping the connection, which the
        caller needs to know since it costs a reconnect.
        """
        return TTSCapabilities(
            streaming=True,
            batch_synthesize=False,
            native_interruption=False,
            aligned_transcript=True,
            emotion_control=False,
            speed_control=True,
            voice_cloning=False,
            context_continuity=True,
        )

    @property
    def is_connected(self) -> bool:
        return self._ws is not None

    @property
    def is_turn_complete(self) -> bool:
        return self._turn_complete

    # ---- lifecycle ---------------------------------------------------

    def url(self) -> str:
        from urllib.parse import urlencode

        query = urlencode(self.query_params())
        return (
            f"wss://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.config.voice}/stream-input?{query}"
        )

    def initial_message(self) -> dict[str, Any]:
        """The handshake frame.

        A single space is the documented initialiser — the vendor requires a
        first `text` before settings take effect.
        """
        message: dict[str, Any] = {
            "text": " ",
            "xi_api_key": self._api_key,
        }
        settings = self.voice_settings()
        if settings:
            message["voice_settings"] = settings
        return message

    async def connect(self) -> object:
        import websockets

        self._ws = await websockets.connect(self.url())
        await self._ws.send(json.dumps(self.initial_message()))
        self._turn_complete = False
        logger.info("ElevenLabs TTS connected (voice=%s)", self.config.voice)
        return self._ws

    async def disconnect(self) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.close()
        finally:
            self._ws = None

    # ---- streaming ---------------------------------------------------

    async def send_text(self, text: str) -> None:
        if self._ws is None:
            raise RuntimeError("ElevenLabs TTS is not connected")
        self._turn_complete = False
        await self._ws.send(json.dumps({"text": text}))

    async def flush(self) -> None:
        """Force generation without closing the stream.

        A real implementation rather than the no-op the migration audit
        anticipated: ElevenLabs documents `{"flush": true}` for exactly this.
        """
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"text": "", "flush": True}))

    async def keepalive(self) -> None:
        """A space keeps the socket warm without generating audio."""
        if self._ws is not None:
            await self._ws.send(json.dumps({"text": " "}))

    async def receive_audio(self) -> bytes | None:
        """Next audio chunk, or None when the turn is finished.

        `isFinal` marks the end of a turn, which is what `is_turn_complete`
        reports — the contract member added because the pipeline was reading it
        through a `getattr` the ABC never named.
        """
        if self._ws is None:
            return None

        import base64

        raw = await self._ws.recv()
        message = json.loads(raw) if isinstance(raw, (str, bytes)) else raw

        if message.get("isFinal"):
            self._turn_complete = True
            return None
        audio = message.get("audio")
        return base64.b64decode(audio) if audio else None

    async def handle_interruption(self) -> None:
        """Drop the connection.

        The websocket has no cancel frame, so stopping mid-turn means closing —
        which is why `capabilities.native_interruption` is false. The caller
        reconnects, and reporting that honestly is better than a no-op that
        leaves audio playing.
        """
        await self.disconnect()
        self._turn_complete = True
