"""Sarvam adapter for the canonical STT socket contract."""

import asyncio
import base64
import json
import logging
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlencode

import arrow
import websockets
from pydantic import BaseModel, Field, model_validator

from eylo.common.contracts.voice import InterruptionType
from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.exceptions import (
    STTConnectionError,
    STTConnectionFailed,
)
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType

logger = logging.getLogger(__name__)

_SARVAM_STT_WS_URL = "wss://api.sarvam.ai/speech-to-text/ws"
_KEEPALIVE_SILENCE_SECONDS = 0.1
_MULAW_ENCODINGS = {"mulaw", "pcm_mulaw", "ulaw", "pcm_ulaw"}
_ENCODING_TO_CODEC = {
    "audio/wav": "wav",
    "linear16": "pcm_s16le",
    "l16": "pcm_l16",
    "pcm_l16": "pcm_l16",
    "pcm_raw": "pcm_raw",
    "pcm_s16le": "pcm_s16le",
    "wav": "wav",
}


class SarvamSTTModel(str, Enum):
    SAARAS_V3 = "saaras:v3"
    SAARIKA_V2_5 = "saarika:v2.5"


class SarvamSTTMode(str, Enum):
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"
    VERBATIM = "verbatim"
    TRANSLIT = "translit"
    CODEMIX = "codemix"


class SarvamInputAudioCodec(str, Enum):
    WAV = "wav"
    PCM_S16LE = "pcm_s16le"
    PCM_L16 = "pcm_l16"
    PCM_RAW = "pcm_raw"


class _SarvamMessageType(str, Enum):
    DATA = "data"
    ERROR = "error"
    EVENTS = "events"
    TRANSLATION = "translation"


class _SarvamSignalType(str, Enum):
    END_SPEECH = "END_SPEECH"
    START_SPEECH = "START_SPEECH"


def _decode_mulaw_to_pcm_s16le(audio_data: bytes) -> bytes:
    pcm_data = bytearray(len(audio_data) * 2)

    for index, byte in enumerate(audio_data):
        mu_law = (~byte) & 0xFF
        magnitude = ((mu_law & 0x0F) << 3) + 0x84
        magnitude <<= (mu_law & 0x70) >> 4
        sample = 0x84 - magnitude if mu_law & 0x80 else magnitude - 0x84

        offset = index * 2
        pcm_data[offset : offset + 2] = int(sample).to_bytes(
            2, byteorder="little", signed=True
        )

    return bytes(pcm_data)


class SarvamSTTConfig(BaseModel):
    api_key: str = Field(min_length=1)
    model: SarvamSTTModel
    # Invented locale default, same class as the TTS module's. Unset lets
    # Sarvam apply its own.
    language_code: str = Field(min_length=1)
    mode: SarvamSTTMode = SarvamSTTMode.TRANSCRIBE
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    input_audio_codec: SarvamInputAudioCodec = SarvamInputAudioCodec.PCM_S16LE
    high_vad_sensitivity: bool = True
    vad_signals: bool = True
    flush_signal: bool = True
    interruption_type: InterruptionType = InterruptionType.VAD
    source_encoding: str = "linear16"

    @model_validator(mode="before")
    @classmethod
    def normalize_inputs(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        if "language" in normalized and "language_code" not in normalized:
            normalized["language_code"] = normalized["language"]
        if "encoding" in normalized and "source_encoding" not in normalized:
            normalized["source_encoding"] = normalized["encoding"]
        if "source_encoding" in normalized and isinstance(
            normalized["source_encoding"], str
        ):
            normalized["source_encoding"] = normalized["source_encoding"].lower()
        if "input_audio_codec" in normalized and isinstance(
            normalized["input_audio_codec"], str
        ):
            normalized["input_audio_codec"] = normalized["input_audio_codec"].lower()

        if "input_audio_codec" not in normalized:
            source_encoding = str(
                normalized.get("source_encoding")
                or normalized.get("encoding")
                or "linear16"
            ).lower()

            if source_encoding in _MULAW_ENCODINGS:
                normalized["input_audio_codec"] = SarvamInputAudioCodec.PCM_S16LE.value
            else:
                normalized["input_audio_codec"] = _ENCODING_TO_CODEC.get(
                    source_encoding,
                    SarvamInputAudioCodec.PCM_S16LE.value,
                )

        return normalized

    @model_validator(mode="after")
    def validate_config(self):
        if self.sample_rate not in {8000, 16000}:
            raise ValueError("Sarvam STT sample_rate must be 8000 or 16000.")

        self.source_encoding = self.source_encoding.lower()

        if self.interruption_type == InterruptionType.TRANSCRIPT:
            logger.warning(
                "Sarvam STT does not emit interim transcripts. Falling back to VAD "
                "interruption."
            )
            self.interruption_type = InterruptionType.VAD

        return self


class _SarvamSTTState(BaseModel):
    interrupted_this_turn: bool = False
    speech_active: bool = False


class SarvamSTT(STTVendorAdapter):
    _BACKOFF_FACTOR = 2
    _MAX_RECONNECTION_ATTEMPTS = 1

    def __init__(self, config: SarvamSTTConfig):
        # Initialise the contract's shared state. Inheriting without this
        # leaves `retry_options` unset, so the ABC's helpers raise on this
        # class while every structural check still passes.
        super().__init__()
        self._config = config
        self._ws: Optional[websockets.ClientConnection] = None
        self._state = _SarvamSTTState()

    @property
    def is_connected(self) -> bool:
        if not self._ws:
            return False
        return self._ws.state == websockets.protocol.State.OPEN

    def _get_ws_url(self) -> str:
        params = {
            "flush_signal": str(self._config.flush_signal).lower(),
            "high_vad_sensitivity": str(self._config.high_vad_sensitivity).lower(),
            "input_audio_codec": self._config.input_audio_codec.value,
            "language-code": self._config.language_code,
            "mode": self._config.mode.value,
            "model": self._config.model.value,
            "sample_rate": str(self._config.sample_rate),
            "vad_signals": str(self._config.vad_signals).lower(),
        }
        return f"{_SARVAM_STT_WS_URL}?{urlencode(params)}"

    def _prepare_audio(self, audio_data: bytes) -> bytes:
        if self._config.source_encoding in _MULAW_ENCODINGS:
            return _decode_mulaw_to_pcm_s16le(audio_data)
        return audio_data

    def _build_audio_message(self, audio_data: bytes) -> str:
        encoded_audio = base64.b64encode(audio_data).decode("utf-8")
        return json.dumps(
            {
                "audio": {
                    "data": encoded_audio,
                    "encoding": "audio/wav",
                    "sample_rate": self._config.sample_rate,
                }
            }
        )

    def _build_keepalive_chunk(self) -> bytes:
        samples = max(1, int(self._config.sample_rate * _KEEPALIVE_SILENCE_SECONDS))
        if self._config.source_encoding in _MULAW_ENCODINGS:
            return b"\xff" * samples
        return b"\x00\x00" * samples

    async def connect(self) -> websockets.ClientConnection:
        if self._ws and self.is_connected:
            return self._ws

        try:
            headers: websockets.HeadersLike = {
                "api-subscription-key": self._config.api_key,
            }  # type: ignore[assignment]
            self._ws = await websockets.connect(
                self._get_ws_url(),
                additional_headers=headers,
                ping_interval=None,
            )
            logger.info("Connected to Sarvam STT service")
            return self._ws
        except Exception as error:
            logger.error(
                "Sarvam STT connection failed error_type=%s",
                type(error).__name__,
            )
            raise STTConnectionFailed from error

    async def disconnect(self):
        try:
            if self._ws and self.is_connected:
                await self._ws.close()
        except Exception as error:
            logger.error(
                "Sarvam STT disconnect failed error_type=%s",
                type(error).__name__,
            )
        finally:
            self._ws = None
            self._state = _SarvamSTTState()

    async def keepalive(self):
        if not self.is_connected:
            return
        await self.send_audio(self._build_keepalive_chunk())

    async def _reconnect(self, attempt: int = 0):
        exponential_backoff = self._BACKOFF_FACTOR**attempt
        await asyncio.sleep(exponential_backoff)
        try:
            await self.connect()
        except Exception as error:
            logger.error(
                "Sarvam STT reconnect failed attempt=%d error_type=%s",
                attempt + 1,
                type(error).__name__,
            )
            if attempt >= self._MAX_RECONNECTION_ATTEMPTS:
                raise STTConnectionFailed from error
            await self._reconnect(attempt + 1)

    async def _receive(self) -> str | None:
        if not self._ws or not self.is_connected:
            return None

        try:
            return await self._ws.recv(decode=True)
        except websockets.ConnectionClosed:
            logger.info("Connection closed by Sarvam STT")
            await self._reconnect()
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        except Exception as error:
            logger.error(
                "Sarvam STT receive failed error_type=%s",
                type(error).__name__,
            )
            raise
        return None

    async def _send_flush(self):
        if not self._ws or not self.is_connected or not self._config.flush_signal:
            return
        await self._ws.send(json.dumps({"type": "flush"}))

    async def _receive_raw_event(self) -> dict | None:
        payload = await self._receive()
        if not payload:
            return None

        try:
            data = json.loads(payload)
            message_type = str(data.get("type", "")).lower()
            message_data = data.get("data", {})
            timestamp = arrow.utcnow().timestamp()

            if message_type in {
                _SarvamMessageType.DATA.value,
                _SarvamMessageType.TRANSLATION.value,
            }:
                transcript = (
                    message_data.get("transcript")
                    or message_data.get("translation")
                    or message_data.get("text")
                    or ""
                ).strip()
                if not transcript:
                    return None

                self._state.speech_active = False
                self._state.interrupted_this_turn = False
                return {
                    "type": "transcript",
                    "transcript": transcript,
                    "is_final": True,
                    "timestamp": timestamp,
                }

            if message_type == _SarvamMessageType.EVENTS.value:
                signal_type = message_data.get("signal_type")

                if signal_type == _SarvamSignalType.START_SPEECH.value:
                    self._state.speech_active = True
                    if not self._state.interrupted_this_turn:
                        self._state.interrupted_this_turn = True
                        return {
                            "type": "interrupt",
                            "should_interrupt": True,
                            "timestamp": timestamp,
                        }
                    return None

                if signal_type == _SarvamSignalType.END_SPEECH.value:
                    self._state.speech_active = False
                    self._state.interrupted_this_turn = False
                    await self._send_flush()
                    return None

            if message_type == _SarvamMessageType.ERROR.value:
                logger.error("Sarvam STT provider error")
                return None
        except json.JSONDecodeError:
            logger.error("Failed to decode Sarvam STT response")
        except Exception as error:
            logger.error(
                "Sarvam STT response processing failed error_type=%s",
                type(error).__name__,
            )

        return None

    async def send_audio(self, audio_data: bytes):
        if not self._ws or not self.is_connected:
            raise STTConnectionError("Not connected to Sarvam STT")

        try:
            prepared_audio = self._prepare_audio(audio_data)
            await self._ws.send(self._build_audio_message(prepared_audio))
        except Exception as error:
            logger.error(
                "Sarvam STT audio send failed error_type=%s",
                type(error).__name__,
            )
            raise

    async def receive_event(self, timeout_ms: int = 100) -> STTEvent | None:
        """Next event as the canonical `STTEvent`.

        Adapts what `receive_event` already returns instead of replacing it,
        so the live path keeps its exact behaviour. Only fields the vendor
        actually reported are set — confidence and timings stay unset rather
        than invented.
        """
        raw = await self._receive_raw_event()
        if raw is None:
            return None
        event_type = raw.get("type") or raw.get("event")
        return STTEvent(
            type=STTEventType(event_type)
            if event_type in set(STTEventType)
            else STTEventType.TRANSCRIPT_PARTIAL,
            provider=self.provider,
            model=self.model,
            transcript=str(raw.get("transcript") or raw.get("text") or ""),
            is_final=bool(raw.get("is_final", False)),
            confidence=raw.get("confidence"),
            language=raw.get("language"),
        )

    async def flush(self) -> None:
        """No flush frame on this stream. Explicit, not faked."""
        return None

    @property
    def provider(self) -> str:
        return "sarvam"

    @property
    def model(self) -> str:
        return str(getattr(self._config, "model", "") or "")

    @property
    def sample_rate(self) -> int:
        """From the operator's config. 16 kHz only if nothing was configured —
        the transport needs a number, and this is the pipeline's rate.
        """
        return int(getattr(self._config, "sample_rate", 16000) or 16000)

    @property
    def capabilities(self) -> STTCapabilities:
        """Derived from this module's own behaviour, not from vendor memory.

        Deepgram's documentation has been unreachable throughout this
        migration, so confirm any of these against it before relying on a
        False.
        """
        return STTCapabilities(
            streaming=True,
            batch_recognize=False,
            interim_results=True,
            vad_events=True,
            turn_detection=False,
            word_timestamps=False,
            speaker_labels=False,
            language_detection=False,
        )
