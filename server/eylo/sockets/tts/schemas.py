"""Data contracts for the `tts` socket."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_TTS_SAMPLE_RATE = 24000
DEFAULT_TTS_ENCODING = "pcm_s16le"

_RAW_CONTAINER_ALIASES = {"none": "raw", "raw": "raw"}
_AUDIO_ENCODING_ALIASES = {
    "alaw": "pcm_alaw",
    "a-law": "pcm_alaw",
    "linear16": "pcm_s16le",
    "linear_16": "pcm_s16le",
    "mulaw": "pcm_mulaw",
    "mu-law": "pcm_mulaw",
    "pcm": "pcm_s16le",
    "pcm_alaw": "pcm_alaw",
    "pcm_mulaw": "pcm_mulaw",
    "pcm_s16le": "pcm_s16le",
    "s16le": "pcm_s16le",
    "ulaw": "pcm_mulaw",
}


class TTSProvider(str, Enum):
    AMAZON_POLLY = "amazon-polly"
    CARTESIA = "cartesia"
    DEEPGRAM = "deepgram"
    ELEVENLABS = "elevenlabs"
    GROQ = "groq"
    HUME = "hume"
    MURF = "murf"
    OPENAI = "openai"
    RIME = "rime"
    SARVAM = "sarvam"
    SMALLEST = "smallest"


_AMAZON_POLLY_FALLBACK_SAMPLE_RATE = 16000


class RetryOptions(BaseModel):
    """Retry behavior for vendor connection and synthesis operations."""

    max_retries: int = Field(default=3, ge=0)
    timeout_seconds: float = Field(default=10.0, gt=0)
    retry_interval_seconds: float = Field(default=1.0, ge=0)


class TTSCapabilities(BaseModel):
    """Static vendor capabilities used by the manager and transports."""

    model_config = ConfigDict(frozen=True)

    streaming: bool = True
    batch_synthesize: bool = False
    native_interruption: bool = False
    aligned_transcript: bool = False
    emotion_control: bool = False
    speed_control: bool = False
    voice_cloning: bool = False
    context_continuity: bool = False
    word_timestamps: bool = False
    sample_rates: tuple[int, ...] = (DEFAULT_TTS_SAMPLE_RATE,)
    languages_count: int = 1


class TTSAudioFormat(BaseModel):
    """Actual raw audio emitted by one TTS adapter.

    This is deliberately separate from a transport's requested output format.
    A provider may ignore or not support the carrier codec, so the pipeline
    converts between these two explicit contracts instead of treating request
    metadata as proof of the bytes returned.
    """

    model_config = ConfigDict(frozen=True)

    container: Literal["raw"]
    encoding: Literal["pcm_s16le", "pcm_mulaw", "pcm_alaw"]
    sample_rate: int = Field(gt=0)
    channels: Literal[1] = 1

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        container = normalized.get("container")
        encoding = normalized.get("encoding")
        if isinstance(container, str):
            normalized["container"] = _RAW_CONTAINER_ALIASES.get(
                container.strip().lower(),
                container.strip().lower(),
            )
        if isinstance(encoding, str):
            normalized["encoding"] = _AUDIO_ENCODING_ALIASES.get(
                encoding.strip().lower(),
                encoding.strip().lower(),
            )
        return normalized

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "TTSAudioFormat":
        """Validate a complete provider or transport media contract."""
        return cls.model_validate(value)


class TTSConfig(BaseModel):
    """Canonical TTS runtime configuration plus provider-specific options."""

    model_config = ConfigDict(extra="allow")

    vendor: TTSProvider | str
    model: str | None = None
    voice: str | None = None
    language: str | None = None
    sample_rate: int = DEFAULT_TTS_SAMPLE_RATE
    encoding: str = DEFAULT_TTS_ENCODING
    output_format: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    retry: RetryOptions = Field(default_factory=RetryOptions)

    @model_validator(mode="before")
    @classmethod
    def normalize_transport_format(cls, data: Any) -> Any:
        if isinstance(data, TTSConfig):
            return data
        if data is None:
            return {}
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        output_format = normalized.get("output_format")
        if isinstance(output_format, dict):
            sample_rate = output_format.get("sample_rate")
            encoding = output_format.get("encoding")
            if isinstance(sample_rate, int) and "sample_rate" not in normalized:
                normalized["sample_rate"] = sample_rate
            if isinstance(encoding, str) and "encoding" not in normalized:
                normalized["encoding"] = encoding

        return normalized

    def to_adapter_config(self) -> dict[str, Any]:
        """Flatten canonical and vendor-specific fields for one adapter."""
        data = self.model_dump(mode="python", exclude_none=True)
        vendor = (
            self.vendor.value if isinstance(self.vendor, TTSProvider) else self.vendor
        )
        data["vendor"] = vendor
        data["retry"] = self.retry.model_dump()
        return data


class TTSAudioChunk(BaseModel):
    """Canonical audio chunk carried inside the TTS manager."""

    data: bytes
    is_final: bool = False
    segment_id: str | None = None
    request_id: str | None = None
    delta_text: str | None = None
    sample_rate: int | None = None
    encoding: str | None = None
    vendor_metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_response(
        cls,
        response: bytes | bytearray | memoryview | "TTSAudioChunk",
        *,
        sample_rate: int | None = None,
        encoding: str | None = None,
        request_id: str | None = None,
    ) -> "TTSAudioChunk":
        if isinstance(response, cls):
            updates: dict[str, Any] = {}
            if response.sample_rate is None and sample_rate is not None:
                updates["sample_rate"] = sample_rate
            if response.encoding is None and encoding is not None:
                updates["encoding"] = encoding
            if response.request_id is None and request_id is not None:
                updates["request_id"] = request_id
            if updates:
                return response.model_copy(update=updates)
            return response
        return cls(
            data=bytes(response),
            sample_rate=sample_rate,
            encoding=encoding,
            request_id=request_id,
        )


class TTSEvent(BaseModel):
    """Vendor-agnostic TTS event for future transcript and telemetry paths."""

    type: Literal["audio", "started", "final", "interrupted", "error", "metadata"]
    vendor: TTSProvider | str
    request_id: str | None = None
    chunk: TTSAudioChunk | None = None
    message: str | None = None
    vendor_metadata: dict[str, Any] = Field(default_factory=dict)


class TTSMetricsSnapshot(BaseModel):
    """Lightweight in-memory metrics snapshot for one TTSRealtime instance."""

    vendor: str
    chunks: int = 0
    bytes: int = 0
    first_audio_latency_seconds: float | None = None
    interruptions: int = 0
    request_drops: int = 0
    response_drops: int = 0
    consumer_drops: int = 0
    errors: int = 0
    total_requests_processed: int = 0
    total_responses_processed: int = 0
    start_time: float
    last_activity: float


def normalize_tts_config(
    config: TTSConfig | dict[str, Any] | None,
    *,
    vendor: str | TTSProvider | None = None,
) -> TTSConfig:
    """Normalize a provider-config mapping into the canonical TTS contract."""
    data: dict[str, Any]
    if isinstance(config, TTSConfig):
        data = config.to_adapter_config()
    elif isinstance(config, dict):
        data = dict(config)
    else:
        data = {}

    configured_vendor = data.get("vendor")
    if isinstance(configured_vendor, TTSProvider):
        configured_vendor = configured_vendor.value
    selected_vendor = (
        configured_vendor.strip()
        if isinstance(configured_vendor, str)
        else None
    )
    if vendor is not None:
        requested_vendor = (
            vendor.value if isinstance(vendor, TTSProvider) else vendor.strip()
        )
        if (
            selected_vendor is not None
            and selected_vendor != requested_vendor
        ):
            raise ValueError(
                "TTS provider config does not match the selected provider."
            )
        selected_vendor = requested_vendor
        data["vendor"] = requested_vendor

    _apply_provider_sample_rate_default(data, selected_vendor)
    return TTSConfig.model_validate(data)


def _apply_provider_sample_rate_default(
    data: dict[str, Any],
    vendor: str | None,
) -> None:
    if vendor != TTSProvider.AMAZON_POLLY.value or "sample_rate" in data:
        return
    output_format = data.get("output_format")
    if isinstance(output_format, dict) and isinstance(
        output_format.get("sample_rate"), int
    ):
        return
    data["sample_rate"] = _AMAZON_POLLY_FALLBACK_SAMPLE_RATE
