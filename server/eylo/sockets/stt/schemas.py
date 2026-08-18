"""Typed contracts for the STT socket module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from time import monotonic
from typing import Any, Mapping

import arrow


class STTProvider(StrEnum):
    """Known STT provider identifiers."""

    AMAZON_TRANSCRIBE = "amazon-transcribe"
    DEEPGRAM = "deepgram"
    DEEPGRAM_FLUX = "deepgram-flux"
    ASSEMBLYAI = "assemblyai"
    CARTESIA = "cartesia"
    GLADIA = "gladia"
    GOOGLE = "google"
    REVAI = "revai"
    SARVAM = "sarvam"
    SPEECHMATICS = "speechmatics"


class STTEncoding(StrEnum):
    """Audio encodings accepted at the STT boundary."""

    LINEAR16 = "linear16"
    PCM_S16LE = "pcm_s16le"
    MULAW = "mulaw"
    ALAW = "alaw"


class STTTurnDetection(StrEnum):
    """Turn detection ownership for an STT session."""

    VENDOR = "vendor"
    INTERNAL = "internal"
    NONE = "none"


class STTEndpointingMode(StrEnum):
    """Endpointing strategy for end-of-turn detection."""

    FIXED = "fixed"
    DYNAMIC = "dynamic"


class STTEventType(StrEnum):
    """Canonical STT event types plus websocket projection types."""

    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_PREFLIGHT = "transcript_preflight"
    TRANSCRIPT_FINAL = "transcript_final"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    START_OF_TURN = "start_of_turn"
    END_OF_TURN = "end_of_turn"
    RECOGNITION_USAGE = "recognition_usage"
    ERROR = "error"

    # Current downstream websocket contract.
    TRANSCRIPT = "transcript"
    VAD = "vad"


class STTVADEventKind(StrEnum):
    """VAD event kinds consumed by websocket handlers."""

    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"
    TURN_RESUMED = "turn_resumed"


class STTTranscriptKind(StrEnum):
    """Transcript event kinds consumed by websocket handlers."""

    FINAL = "final"
    PARTIAL = "partial"
    PREFLIGHT = "preflight"


@dataclass(frozen=True)
class RetryOptions:
    """Retry policy for STT operations."""

    max_retry: int = 3
    timeout: float = 10.0
    retry_interval: float = 1.0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "RetryOptions":
        """Build retry options from an optional dict."""
        if not value:
            return cls()
        return cls(
            max_retry=int(value.get("max_retry", cls.max_retry)),
            timeout=float(value.get("timeout", cls.timeout)),
            retry_interval=float(value.get("retry_interval", cls.retry_interval)),
        )


@dataclass(frozen=True)
class STTCapabilities:
    """Vendor capability declaration used by the manager and tests."""

    streaming: bool = True
    batch_recognize: bool = False
    interim_results: bool = True
    vad_events: bool = False
    turn_detection: bool = False
    word_timestamps: bool = False
    speaker_labels: bool = False
    language_detection: bool = False
    custom_vocabulary: bool = False
    punctuation: bool = False
    profanity_filter: bool = False
    aligned_transcript: str | bool = False
    supported_encodings: tuple[str, ...] = (
        STTEncoding.LINEAR16.value,
        STTEncoding.PCM_S16LE.value,
    )
    supported_sample_rates: tuple[int, ...] = (8000, 16000, 44100, 48000)


@dataclass(frozen=True)
class TimedWord:
    """A transcript token with optional timing and confidence."""

    word: str
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float = 0.0


@dataclass(frozen=True)
class RecognitionUsage:
    """Usage payload emitted by providers that report cost dimensions."""

    audio_duration: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class STTError:
    """Structured STT error details."""

    message: str
    recoverable: bool = True
    code: str | None = None


@dataclass(frozen=True)
class STTConfig:
    """Typed STT configuration with vendor-option passthrough."""

    vendor: str
    model: str = ""
    language: str | None = None
    sample_rate: int = 16000
    encoding: str = STTEncoding.LINEAR16.value
    interim_results: bool = True
    vad_enabled: bool = True
    turn_detection: str = STTTurnDetection.VENDOR.value
    endpointing_mode: str = STTEndpointingMode.FIXED.value
    eot_threshold: float = 0.85
    eot_timeout_ms: int = 5000
    custom_vocabulary: tuple[str, ...] = ()
    word_timestamps: bool = True
    speaker_labels: bool = False
    batch_enabled: bool = False
    retry: RetryOptions = field(default_factory=RetryOptions)
    vendor_options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        value: "STTConfig | Mapping[str, Any] | None",
        *,
        vendor: str | None = None,
    ) -> "STTConfig":
        """Normalize a provider-config mapping into the typed STT contract."""
        if isinstance(value, cls):
            if vendor is not None and vendor.strip() != value.vendor:
                raise ValueError(
                    "STT provider config does not match the selected provider."
                )
            return value

        data = dict(value or {})
        configured_vendor = data.pop("vendor", None)
        if (
            vendor is not None
            and configured_vendor is not None
            and vendor.strip() != configured_vendor
        ):
            raise ValueError(
                "STT provider config does not match the selected provider."
            )
        selected_vendor_value = vendor if vendor is not None else configured_vendor
        if (
            not isinstance(selected_vendor_value, str)
            or not selected_vendor_value.strip()
        ):
            raise ValueError("STT provider is required.")
        selected_vendor = selected_vendor_value.strip()

        if "encoding" not in data and data.get("input_audio_codec"):
            data["encoding"] = data["input_audio_codec"]
        if "eot_timeout_ms" not in data and data.get("utterance_end_ms"):
            data["eot_timeout_ms"] = data["utterance_end_ms"]

        retry = RetryOptions.from_mapping(data.pop("retry", None))
        vocabulary = data.pop("custom_vocabulary", ()) or ()
        if isinstance(vocabulary, list):
            vocabulary = tuple(str(item) for item in vocabulary)

        known_fields = {
            "model",
            "language",
            "sample_rate",
            "encoding",
            "interim_results",
            "vad_enabled",
            "turn_detection",
            "endpointing_mode",
            "eot_threshold",
            "eot_timeout_ms",
            "word_timestamps",
            "speaker_labels",
            "batch_enabled",
        }
        base = {
            field_name: data.pop(field_name)
            for field_name in list(data)
            if field_name in known_fields
        }

        return cls(
            vendor=selected_vendor,
            retry=retry,
            custom_vocabulary=tuple(vocabulary),
            vendor_options=data,
            **base,
        )

    def to_adapter_config(self) -> dict[str, Any]:
        """Flatten canonical and vendor-specific fields for one adapter."""
        config = dict(self.vendor_options)
        config.update(
            {
                "vendor": self.vendor,
                "language": self.language,
                "sample_rate": self.sample_rate,
                "encoding": self.encoding,
                "interim_results": self.interim_results,
                "vad_enabled": self.vad_enabled,
                "turn_detection": self.turn_detection,
                "endpointing_mode": self.endpointing_mode,
                "eot_threshold": self.eot_threshold,
                "eot_timeout_ms": self.eot_timeout_ms,
                "custom_vocabulary": list(self.custom_vocabulary),
                "word_timestamps": self.word_timestamps,
                "speaker_labels": self.speaker_labels,
                "batch_enabled": self.batch_enabled,
            }
        )
        if self.model:
            config["model"] = self.model
        return {key: value for key, value in config.items() if value is not None}


@dataclass(frozen=True)
class STTEvent:
    """Canonical STT event emitted by every provider adapter."""

    type: STTEventType
    session_id: str = ""
    provider: str = ""
    model: str = ""
    transcript: str = ""
    is_final: bool = False
    confidence: float | None = None
    language: str | None = None
    request_id: str | None = None
    provider_request_id: str | None = None
    words: tuple[TimedWord, ...] = ()
    speaker_id: str | None = None
    audio_start_ms: int | None = None
    audio_end_ms: int | None = None
    usage: RecognitionUsage | None = None
    error: STTError | None = None
    timestamp: float = field(default_factory=lambda: arrow.utcnow().timestamp())
    vendor_metadata: dict[str, Any] = field(default_factory=dict)

    def to_platform_event(self) -> dict[str, Any]:
        """Project this event onto the current websocket voice-event shape."""
        base: dict[str, Any] = {
            "timestamp": self.timestamp,
            "vendor_event_type": self.type.value,
        }
        if self.provider:
            base["provider"] = self.provider
        if self.model:
            base["model"] = self.model
        base.update(self.vendor_metadata)

        if self.type == STTEventType.ERROR:
            base["type"] = STTEventType.ERROR.value
            if self.error:
                base["error"] = self.error.message
                base["recoverable"] = self.error.recoverable
                if self.error.code:
                    base["code"] = self.error.code
            return base

        if self.type == STTEventType.RECOGNITION_USAGE:
            base["type"] = STTEventType.RECOGNITION_USAGE.value
            if self.usage:
                base["usage"] = {
                    "audio_duration": self.usage.audio_duration,
                    "input_tokens": self.usage.input_tokens,
                    "output_tokens": self.usage.output_tokens,
                }
            return base

        if self.type in _SPEECH_START_TYPES:
            event = {
                **base,
                "type": STTEventType.VAD.value,
                "event": STTVADEventKind.SPEECH_STARTED.value,
                "should_interrupt": self.vendor_metadata.get(
                    "should_interrupt",
                    self.vendor_metadata.get("vendor_event_type") == "interrupt",
                ),
            }
            if self.transcript:
                event["transcript"] = self.transcript
            return event

        if self.type in _SPEECH_END_TYPES and not self.transcript:
            return {
                **base,
                "type": STTEventType.VAD.value,
                "event": STTVADEventKind.SPEECH_ENDED.value,
                "should_interrupt": False,
            }

        transcript_kind = (
            STTTranscriptKind.FINAL.value
            if self.is_final
            else STTTranscriptKind.PARTIAL.value
        )
        if self.type == STTEventType.TRANSCRIPT_PREFLIGHT:
            transcript_kind = STTTranscriptKind.PREFLIGHT.value

        return {
            **base,
            "type": STTEventType.TRANSCRIPT.value,
            "transcript": self.transcript,
            "transcript_kind": transcript_kind,
            "is_final": self.is_final,
            "confidence": self.confidence,
        }


@dataclass
class STTMetricsSnapshot:
    """Lightweight in-process metrics for STT sessions."""

    request_count: int = 0
    event_count: int = 0
    audio_bytes_sent: int = 0
    error_count: int = 0
    reconnect_count: int = 0
    connected_at: float | None = None
    last_event_at: float | None = None
    last_event_type: str | None = None

    def mark_connected(self) -> None:
        """Record connection start time."""
        self.connected_at = monotonic()

    def mark_audio_sent(self, byte_count: int) -> None:
        """Record a sent audio chunk."""
        self.request_count += 1
        self.audio_bytes_sent += byte_count

    def mark_event(self, event_type: str) -> None:
        """Record a normalized STT event."""
        self.event_count += 1
        self.last_event_type = event_type
        self.last_event_at = monotonic()

    def mark_error(self) -> None:
        """Record an STT error."""
        self.error_count += 1

    def mark_reconnect(self) -> None:
        """Record a reconnect attempt."""
        self.reconnect_count += 1

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable metrics snapshot."""
        return {
            "request_count": self.request_count,
            "event_count": self.event_count,
            "audio_bytes_sent": self.audio_bytes_sent,
            "error_count": self.error_count,
            "reconnect_count": self.reconnect_count,
            "connected_at": self.connected_at,
            "last_event_at": self.last_event_at,
            "last_event_type": self.last_event_type,
        }


_SPEECH_START_TYPES = {
    STTEventType.SPEECH_START,
    STTEventType.START_OF_TURN,
}
_SPEECH_END_TYPES = {
    STTEventType.SPEECH_END,
    STTEventType.END_OF_TURN,
}
