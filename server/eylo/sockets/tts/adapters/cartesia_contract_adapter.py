"""Cartesia implementation of the provider-neutral TTS contract."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from eylo.common.contracts.provider_config import NotConfiguredError
from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.schemas import RetryOptions, TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

PROVIDER = "cartesia"
CARTESIA_VERSION = "2025-04-16"

# Cartesia names its container/encoding explicitly rather than in one string.
DEFAULT_CONTAINER = "raw"
DEFAULT_ENCODING = "pcm_s16le"


class CartesiaContractAdapter(TTSVendorAdapter):
    """Cartesia websocket TTS, contract-first."""

    def __init__(
        self,
        config: TTSConfig,
        retry_options: RetryOptions | None = None,
    ) -> None:
        if str(config.options.get("container") or DEFAULT_CONTAINER) != "raw":
            raise ValueError("Cartesia TTS must emit raw audio for realtime voice.")
        super().__init__(config, retry_options)
        self._ws: Any = None
        self._turn_complete = False
        self._context_id = str(uuid.uuid4())

        missing = []
        self._api_key = str(config.options.get("api_key") or "")
        if not self._api_key:
            missing.append("api_key")
        # All three are required by Cartesia with no vendor default, so all
        # three raise. Defaulting any of them would pick on the operator's
        # behalf — which for `voice` is what their users hear.
        if not config.voice:
            missing.append("voice")
        if not config.model:
            missing.append("model")
        if missing:
            raise NotConfiguredError(
                missing=tuple(missing),
                capability="tts",
                configure_via="/api/tts-configs",
            )

    @property
    def config(self) -> TTSConfig:
        return self._contract_config

    # ---- identity ----------------------------------------------------

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def model(self) -> str:
        return str(self.config.model)

    @property
    def sample_rate(self) -> int:
        return int(self.config.sample_rate)

    @property
    def capabilities(self) -> TTSCapabilities:
        """Stated, not discovered.

        `context_continuity` is the one that matters and is where Cartesia
        genuinely differs from ElevenLabs: a context id lets a later request
        continue the same utterance, which a caller can only use if it knows.
        """
        return TTSCapabilities(
            streaming=True,
            batch_synthesize=False,
            native_interruption=False,
            aligned_transcript=False,
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

    # ---- payloads ----------------------------------------------------

    def output_format(self) -> dict[str, Any]:
        """Required by the vendor, and read by the pipeline for resampling."""
        return {
            "container": str(self.config.options.get("container") or DEFAULT_CONTAINER),
            "encoding": str(self.config.encoding or DEFAULT_ENCODING),
            "sample_rate": int(self.config.sample_rate),
        }

    def url(self) -> str:
        return (
            f"wss://api.cartesia.ai/tts/websocket"
            f"?api_key={self._api_key}&cartesia_version={CARTESIA_VERSION}"
        )

    def request(self, text: str, *, continue_: bool = True) -> dict[str, Any]:
        """One generation request.

        `context_id` is required and identifies the utterance. Holding one per
        adapter is what makes `context_continuity` true: successive requests
        with `continue` set extend the same speech rather than starting over.
        """
        return {
            "model_id": str(self.config.model),
            "transcript": text,
            "voice": {"mode": "id", "id": str(self.config.voice)},
            "output_format": self.output_format(),
            "context_id": self._context_id,
            "continue": continue_,
            **(
                {"language": self.config.language}
                if self.config.language
                else {}
            ),
        }

    # ---- lifecycle ---------------------------------------------------

    async def connect(self) -> object:
        import websockets

        self._ws = await websockets.connect(self.url())
        self._turn_complete = False
        logger.info(
            "Cartesia TTS connected (model=%s voice=%s)",
            self.config.model,
            self.config.voice,
        )
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
            raise RuntimeError("Cartesia TTS is not connected")
        self._turn_complete = False
        await self._ws.send(json.dumps(self.request(text)))

    async def flush(self) -> None:
        """Force generation without ending the context.

        Native, like ElevenLabs and unlike what the migration audit assumed
        before the vendor docs were read. Cartesia answers with a `flush_id`
        that maps audio back to the request that produced it.
        """
        if self._ws is None:
            return
        await self._ws.send(
            json.dumps({"context_id": self._context_id, "flush": True})
        )

    async def keepalive(self) -> None:
        """No keepalive frame exists. Stated rather than faked.

        Cartesia holds the socket open on its own; sending an empty transcript
        would generate audio, which is worse than doing nothing.
        """
        return None

    async def receive_audio(self) -> bytes | None:
        if self._ws is None:
            return None

        import base64

        raw = await self._ws.recv()
        message = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        kind = message.get("type")

        if kind == "done":
            self._turn_complete = True
            return None
        if kind == "error":
            raise RuntimeError(f"Cartesia error: {message.get('error')}")
        data = message.get("data")
        return base64.b64decode(data) if data else None

    async def handle_interruption(self) -> None:
        """End the context and start a new one.

        `continue: false` closes the current utterance without dropping the
        socket, so a new turn does not pay a reconnect — which is why this
        differs from the ElevenLabs adapter, and why `native_interruption`
        stays false for both: neither vendor cancels audio already sent.
        """
        if self._ws is not None:
            await self._ws.send(json.dumps(self.request("", continue_=False)))
        self._context_id = str(uuid.uuid4())
        self._turn_complete = True
