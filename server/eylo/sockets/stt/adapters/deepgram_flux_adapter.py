"""Deepgram Flux adapter for the canonical STT socket contract."""

import asyncio
import json
import logging
from enum import Enum
from typing import Dict, Optional

import arrow
import pydantic
import websockets
from pydantic import BaseModel, Field

from eylo.common.contracts.voice import InterruptionType
from eylo.sockets.stt.base import STTVendorAdapter
from eylo.sockets.stt.exceptions import (
    STTConnectionError,
    STTConnectionFailed,
)
from eylo.sockets.stt.schemas import STTCapabilities, STTEvent, STTEventType

logger = logging.getLogger(__name__)

# Deepgram API constants
_DEEPGRAM_API_URL = "wss://api.deepgram.com/v2/listen"


class _FluxEventType(str, Enum):
    """Deepgram Flux specific event types."""

    StartOfTurn = "StartOfTurn"  # User started talking
    Update = "Update"  # User is still talking...
    EagerEndOfTurn = "EagerEndOfTurn"  # Speculative end of turn (Speedy)
    EndOfTurn = "EndOfTurn"  # Definite end of turn
    TurnResumed = "TurnResumed"  # User started talking again

    # Other Deepgram Events
    Metadata = "Metadata"  # Connected!
    CloseStream = "CloseStream"  # Goodbye!
    Error = "Error"  # Something broke!


class _FluxResponse(BaseModel):
    """Pydantic model for Deepgram Flux responses."""

    type: str  # "TurnInfo", "Metadata", "Error", "CloseStream"
    event: Optional[_FluxEventType] = None
    transcript: str = ""
    turn_index: int = 0
    end_of_turn_confidence: float = 0.0

    # Error fields
    message: Optional[str] = None
    description: Optional[str] = None
    variant: Optional[str] = None

    class Config:
        extra = "ignore"


class DeepgramFluxConfig(BaseModel):
    """Configuration for Deepgram Flux STT service."""

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    # The model name already encodes a language (flux-general-en), so this was
    # both invented and probably redundant. Unset lets the vendor decide.
    language: Optional[str] = None
    # smart_format and punctuate were declared here and never sent — each
    # appeared exactly once in this module, its own field declaration. They are
    # Deepgram *Listen* parameters and Flux is a different product; the
    # They are Deepgram Listen parameters and are intentionally absent here.
    encoding: str = "linear16"
    sample_rate: int = 16000
    channels: int = 1

    # Flux specific settings
    eot_threshold: float = 0.85  # 85% sure the user is done
    eager_eot_threshold: float = 0.5  # 50% sure the user is done (activates Eager mode)
    # 5000 to agree with STTSettings.eot_timeout_ms, which is what the config
    # surface advertises and bounds at le=10000. This said 8000, so one setting
    # had two answers and which an operator got depended on whether the config
    # surface passed a value through.
    eot_timeout_ms: int = 5000

    # Interruption settings
    interruption_type: InterruptionType = InterruptionType.VAD

class _DeepgramFluxState(BaseModel):
    """State tracking for Deepgram Flux connection."""

    reconnect_attempts: int = 0
    speech_active: bool = False
    interrupted_this_turn: bool = False
    eager_handled_turn_index: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True


class DeepgramFluxSTT(STTVendorAdapter):
    """Deepgram Flux STT implementation for low-latency voice agents."""

    _MAX_RECONNECTION_ATTEMPTS = 1
    _BACKOFF_FACTOR = 2

    def __init__(self, config: DeepgramFluxConfig):
        # Initialise the contract's shared state. Inheriting without this
        # leaves `retry_options` unset, so the ABC's helpers raise on this
        # class while every structural check still passes.
        super().__init__()
        self._config = config
        self._ws: websockets.ClientConnection = None
        self._state = _DeepgramFluxState()
        logger.info(
            "Deepgram Flux initialized model=%s encoding=%s sample_rate=%d",
            self._config.model,
            self._config.encoding,
            self._config.sample_rate,
        )

    @property
    def is_connected(self) -> bool:
        if not self._ws:
            return False
        return self._ws.state == websockets.protocol.State.OPEN

    def _get_ws_url(self) -> str:
        """Generate the Deepgram Flux API URL with query parameters."""
        params = {
            "model": self._config.model,
            "sample_rate": self._config.sample_rate,
            "encoding": self._config.encoding,
            # Flux parameters
            "eot_threshold": str(self._config.eot_threshold),
            "eot_timeout_ms": str(self._config.eot_timeout_ms),
        }
        params_str = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{_DEEPGRAM_API_URL}?{params_str}"

    async def keepalive(self):
        """Keepalive is not supported for Flux, skipping."""
        # Note: Flux does not support "type": "KeepAlive"
        pass

    async def connect(self) -> websockets.ClientConnection:
        """Establish a WebSocket connection to Deepgram Flux."""
        if self._ws and self.is_connected:
            return self._ws

        try:
            ws_url = self._get_ws_url()
            logger.info("Connecting to Deepgram Flux")
            headers = {"Authorization": f"Token {self._config.api_key}"}
            self._ws = await websockets.connect(ws_url, additional_headers=headers)
            logger.info("Connected to Deepgram Flux STT service")
            return self._ws
        except Exception as error:
            logger.error(
                "Deepgram Flux connection failed error_type=%s",
                type(error).__name__,
            )
            raise STTConnectionFailed

    async def disconnect(self):
        """Close the WebSocket connection."""
        ws = self._ws
        try:
            if ws and self.is_connected:
                await ws.send(json.dumps({"type": "CloseStream"}))
        except Exception as error:
            logger.error(
                "Deepgram Flux disconnect failed error_type=%s",
                type(error).__name__,
            )
        finally:
            if ws:
                try:
                    await ws.close()
                except Exception as error:
                    logger.error(
                        "Deepgram Flux socket close failed error_type=%s",
                        type(error).__name__,
                    )
            if self._ws is ws:
                self._ws = None
                self._state = _DeepgramFluxState()

    async def _reconnect(self, attempt: int = 0):
        """Attempt to reconnect with exponential backoff."""
        exponential_backoff = self._BACKOFF_FACTOR**attempt
        await asyncio.sleep(exponential_backoff)
        try:
            await self.connect()
        except Exception as error:
            logger.error(
                "Deepgram Flux reconnect failed attempt=%d error_type=%s",
                attempt + 1,
                type(error).__name__,
            )
            if attempt >= self._MAX_RECONNECTION_ATTEMPTS:
                raise STTConnectionFailed
            await self._reconnect(attempt + 1)

    async def _receive(self) -> str | None:
        """Receive a message from the WebSocket connection."""
        try:
            if self._ws and self.is_connected:
                try:
                    return await self._ws.recv(decode=True)
                except websockets.ConnectionClosed:
                    logger.info("Connection closed by Deepgram Flux.")
                    await self._reconnect()
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
        except Exception as error:
            logger.error(
                "Deepgram Flux receive failed error_type=%s",
                type(error).__name__,
            )
            raise
        return None

    async def _receive_raw_event(self) -> Dict | None:
        """Process one Deepgram Flux response into its vendor-shaped event."""
        payload = await self._receive()
        if not payload:
            return None

        try:
            data = _FluxResponse.model_validate_json(payload)
            timestamp = arrow.utcnow().timestamp()

            # Handle Non-Turn Messages
            if data.type == "Metadata":
                logger.info("Deepgram Flux connected")
                return None
            elif data.type == "CloseStream":
                logger.info("Flux Stream Closed.")
                return None
            elif data.type == "Error":
                logger.error("Deepgram Flux provider error")
                return None

            #  StartOfTurn -> Interrupt immediately if VAD mode
            if data.event == _FluxEventType.StartOfTurn:
                logger.info("Flux: StartOfTurn detected")
                self._state.speech_active = True
                self._state.interrupted_this_turn = False  # Reset for new turn

                if self._config.interruption_type == InterruptionType.VAD:
                    logger.info("Flux: Interrupting (VAD mode)")
                    self._state.interrupted_this_turn = True
                    return {"type": "interrupt", "timestamp": timestamp}
                return None

            #  EndOfTurn -> Normal completion (fallback if Eager failed)
            elif data.event == _FluxEventType.EndOfTurn:
                if self._state.eager_handled_turn_index == data.turn_index:
                    logger.info("Flux: EndOfTurn ignored (already handled eagerly)")
                    return None

                logger.info(
                    "Flux: EndOfTurn transcript_chars=%d",
                    len(data.transcript),
                )
                self._state.speech_active = False
                self._state.interrupted_this_turn = False
                return {
                    "type": "transcript",
                    "transcript": data.transcript,
                    "is_final": True,
                    "timestamp": timestamp,
                }

            #  TurnResumed -> False alarm (Interrupt again)
            elif data.event == _FluxEventType.TurnResumed:
                logger.info("Flux: TurnResumed - Cancelling previous turn!")
                self._state.speech_active = True
                self._state.eager_handled_turn_index = None

                # Treat as interrupt regardless of mode to stop any bot response
                return {"type": "interrupt", "timestamp": timestamp}

            #  Regular Updates
            elif data.event == _FluxEventType.Update:
                # Handle TRANSCRIPT based interruption
                if (
                    self._config.interruption_type == InterruptionType.TRANSCRIPT
                    and not self._state.interrupted_this_turn
                    and data.transcript
                ):
                    # We don't have per-update confidence in Flux yet, but if there's text,
                    # it usually means user is speaking.
                    # The plan says "transcript confidence > 0.5".
                    # Flux doesn't provide confidence on Updates, only EOT.
                    # For now, we'll assume if there's a transcript update, we can interrupt.
                    logger.info("Flux: Interrupting (TRANSCRIPT mode)")
                    self._state.interrupted_this_turn = True
                    return {
                        "type": "interrupt",
                        "transcript": data.transcript,
                        "timestamp": timestamp,
                    }

        except pydantic.ValidationError:
            # Fallback for unexpected messages
            pass
        except Exception as error:
            logger.error(
                "Flux response processing failed error_type=%s",
                type(error).__name__,
            )

        return None

    async def send_audio(self, audio_data: bytes):
        """Send audio data to Deepgram Flux."""
        try:
            if self._ws and self.is_connected:
                await self._ws.send(audio_data)
            else:
                raise STTConnectionError("Not connected to Deepgram Flux")
        except Exception as error:
            logger.error(
                "Deepgram Flux audio send failed error_type=%s",
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
        return "deepgram-flux"

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
            turn_detection=True,
            word_timestamps=False,
            speaker_labels=False,
            language_detection=False,
        )
