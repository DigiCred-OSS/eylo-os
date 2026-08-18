"""Sarvam implementation of the provider-neutral TTS contract."""

from __future__ import annotations

import json
import logging
from typing import Any

from eylo.common.contracts.provider_config import NotConfiguredError
from eylo.sockets.tts.base import TTSVendorAdapter
from eylo.sockets.tts.schemas import RetryOptions, TTSCapabilities, TTSConfig

logger = logging.getLogger(__name__)

PROVIDER = "sarvam"

# Vendor-documented: which tuning parameters each model actually honours.
# Sending an unhonoured one is not an error at Sarvam — it is ignored — which is
# precisely why the platform has to say something about it.
_V3 = "bulbul:v3"
_IGNORED_ON_V3 = ("pitch", "loudness")
_V3_ONLY = ("temperature",)

_TUNING_KEYS = ("pitch", "pace", "loudness", "temperature")


class SarvamContractAdapter(TTSVendorAdapter):
    """Sarvam websocket TTS, contract-first."""

    def __init__(
        self,
        config: TTSConfig,
        retry_options: RetryOptions | None = None,
    ) -> None:
        super().__init__(config, retry_options)
        self._ws: Any = None
        self._turn_complete = False

        options = config.options
        missing = []
        self._api_key = str(options.get("api_key") or "")
        if not self._api_key:
            missing.append("api_key")
        if not config.model:
            missing.append("model")
        # Required by Sarvam. `voice` is the contract's word for what Sarvam
        # calls `speaker`; the factory maps the name so this adapter speaks one
        # vocabulary.
        if not config.voice:
            missing.append("voice")
        # Required, and the one whose invented default has the loudest
        # consequence: it decides what language the caller's users hear.
        if not config.language:
            missing.append("language")
        if missing:
            raise NotConfiguredError(
                missing=tuple(missing),
                capability="tts",
                configure_via="/api/tts-configs",
            )
        self._model = str(config.model)

    @property
    def config(self) -> TTSConfig:
        return self._contract_config

    # ---- identity ----------------------------------------------------

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def model(self) -> str:
        return self._model

    @property
    def sample_rate(self) -> int:
        configured = self.config.options.get("speech_sample_rate")
        if configured is not None:
            return int(configured)
        return 24000 if self._model == _V3 else 22050

    @property
    def capabilities(self) -> TTSCapabilities:
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

    @property
    def is_connected(self) -> bool:
        return self._ws is not None

    @property
    def is_turn_complete(self) -> bool:
        return self._turn_complete

    # ---- model-conditional configuration -----------------------------

    def unsupported_options(self) -> tuple[str, ...]:
        """Operator settings this model will ignore.

        Reported rather than raised. Raising would break an operator who moved
        working v2 settings onto v3 and is otherwise fine; staying silent is the
        behaviour this platform exists to remove. Naming them lets a caller say
        which settings are doing nothing.
        """
        options = self.config.options
        keys = _IGNORED_ON_V3 if self._model == _V3 else _V3_ONLY
        return tuple(key for key in keys if options.get(key) is not None)

    def tuning(self) -> dict[str, Any]:
        """Only what the operator set *and* this model honours.

        Vendor defaults are never restated: pace 1.0 and temperature 0.6 are
        Sarvam's, and copying them here would pin their old values the day
        Sarvam changes them.
        """
        ignored = set(self.unsupported_options())
        options = self.config.options
        return {
            key: options[key]
            for key in _TUNING_KEYS
            if options.get(key) is not None and key not in ignored
        }

    # ---- payloads ----------------------------------------------------

    def url(self) -> str:
        return f"wss://api.sarvam.ai/text-to-speech/ws?model={self._model}"

    def initial_message(self) -> dict[str, Any]:
        unsupported = self.unsupported_options()
        if unsupported:
            logger.warning(
                "Sarvam model %s ignores these configured options: %s. They are "
                "omitted from the request.",
                self._model,
                ", ".join(unsupported),
            )
        config: dict[str, Any] = {
            "target_language_code": str(self.config.language),
            "speaker": str(self.config.voice),
            **self.tuning(),
        }
        # Omitted when unset so Sarvam applies its own per-model default —
        # 22050 for v2, 24000 for v3 — rather than a number we chose.
        if self.config.options.get("speech_sample_rate") is not None:
            config["speech_sample_rate"] = int(
                self.config.options["speech_sample_rate"]
            )
        return {"type": "config", "data": config}

    # ---- lifecycle ---------------------------------------------------

    async def connect(self) -> object:
        import websockets

        self._ws = await websockets.connect(
            self.url(), additional_headers={"api-subscription-key": self._api_key}
        )
        await self._ws.send(json.dumps(self.initial_message()))
        self._turn_complete = False
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
            raise RuntimeError("Sarvam TTS is not connected")
        self._turn_complete = False
        await self._ws.send(json.dumps({"type": "text", "data": {"text": text}}))

    async def flush(self) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "flush"}))

    async def keepalive(self) -> None:
        if self._ws is not None:
            await self._ws.send(json.dumps({"type": "ping"}))

    async def receive_audio(self) -> bytes | None:
        if self._ws is None:
            return None

        import base64

        raw = await self._ws.recv()
        message = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        kind = message.get("type")

        if kind in {"flush_done", "done"}:
            self._turn_complete = True
            return None
        if kind == "error":
            raise RuntimeError(f"Sarvam error: {message.get('data')}")
        audio = (message.get("data") or {}).get("audio")
        return base64.b64decode(audio) if audio else None

    async def handle_interruption(self) -> None:
        await self.disconnect()
        self._turn_complete = True
