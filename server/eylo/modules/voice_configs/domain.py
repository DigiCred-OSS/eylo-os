"""Provider-specific validation and resolved runtime values for voice configs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.domain import (
    EffectiveProviderConfig,
    InvalidProviderConfig,
)
from eylo.modules.voice_configs.catalog import (
    AMAZON_NOVA_SONIC_ENDPOINTING_SENSITIVITIES,
    AMAZON_NOVA_SONIC_MODELS,
    AMAZON_NOVA_SONIC_VOICES,
    RealtimeProviders,
    STTProviders,
    TTSProviders,
    VoiceKind,
)

__all__ = [
    "InvalidVoiceConfig",
    "ResolvedRealtime",
    "ResolvedSTT",
    "ResolvedTTS",
    "VoiceProviderConfig",
    "VoiceKind",
]

_SECRET_FIELD_NAME = "api_key"
_GOOGLE_SECRET_FIELD_NAME = "service_account_json"
_AWS_SECRET_FIELDS = frozenset(
    {"access_key_id", "secret_access_key", "session_token"}
)
_AWS_REQUIRED_SECRET_FIELDS = frozenset({"access_key_id", "secret_access_key"})
_AWS_PROVIDERS = frozenset(
    {
        RealtimeProviders.AMAZON_NOVA_SONIC,
        STTProviders.AMAZON_TRANSCRIBE,
        TTSProviders.AMAZON_POLLY,
    }
)
_AWS_REGION_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+-\d+$")
_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2,8}){0,2}$")
_AWS_RESOURCE_NAME_PATTERN = re.compile(r"^[0-9A-Za-z._-]{1,200}$")
_POLLY_ENGINES = frozenset({"standard", "neural", "long-form", "generative"})
_PARTIAL_RESULTS_STABILITIES = frozenset({"low", "medium", "high"})

VoiceProvider = STTProviders | TTSProviders | RealtimeProviders
_ProviderKey = tuple[
    type[STTProviders] | type[TTSProviders] | type[RealtimeProviders],
    str,
]

_CONFIG_FIELDS: dict[_ProviderKey, frozenset[str]] = {
    (RealtimeProviders, RealtimeProviders.AMAZON_NOVA_SONIC.value): frozenset(
        {
            "region",
            "model",
            "voice",
            "max_tokens",
            "temperature",
            "top_p",
            "endpointing_sensitivity",
        }
    ),
    (RealtimeProviders, RealtimeProviders.GEMINI_LIVE.value): frozenset(
        {
            "model",
            "voice",
            "temperature",
            "context_compression_enabled",
            "context_compression_trigger_tokens",
        }
    ),
    (RealtimeProviders, RealtimeProviders.OPENAI_REALTIME.value): frozenset(
        {
            "model",
            "voice",
            "temperature",
            "input_transcription_model",
            "vad_threshold",
            "vad_silence_ms",
        }
    ),
    (STTProviders, STTProviders.AMAZON_TRANSCRIBE.value): frozenset(
        {
            "region",
            "language",
            "partial_results_stability",
            "vocabulary_name",
            "language_model_name",
            "show_speaker_label",
        }
    ),
    (STTProviders, STTProviders.DEEPGRAM.value): frozenset(
        {
            "model",
            "language",
            "sample_rate",
            "encoding",
            "interim_results",
            "punctuate",
            "vad_events",
            "endpointing",
            "utterance_end_ms",
        }
    ),
    (STTProviders, STTProviders.DEEPGRAM_FLUX.value): frozenset(
        {
            "model",
            "sample_rate",
            "encoding",
            "eot_threshold",
            "eot_timeout_ms",
            "high_vad_sensitivity",
        }
    ),
    (STTProviders, STTProviders.SARVAM.value): frozenset(
        {
            "model",
            "language",
            "mode",
            "sample_rate",
            "encoding",
            "input_audio_codec",
            "high_vad_sensitivity",
            "flush_signal",
        }
    ),
    (STTProviders, STTProviders.ASSEMBLYAI.value): frozenset(
        {
            "model",
            "sample_rate",
            "encoding",
            "eot_threshold",
            "eot_timeout_ms",
            "keyterms_prompt",
        }
    ),
    (STTProviders, STTProviders.CARTESIA.value): frozenset(
        {"model", "language", "sample_rate", "encoding"}
    ),
    (STTProviders, STTProviders.GOOGLE.value): frozenset(
        {
            "model",
            "language",
            "sample_rate",
            "interim_results",
            "punctuation",
            "profanity_filter",
            "detect_language",
            "alternative_languages",
        }
    ),
    (STTProviders, STTProviders.GLADIA.value): frozenset(
        {"language", "sample_rate", "encoding", "buffer_size_seconds"}
    ),
    (STTProviders, STTProviders.REVAI.value): frozenset({"language", "sample_rate"}),
    (STTProviders, STTProviders.SPEECHMATICS.value): frozenset(
        {
            "language",
            "sample_rate",
            "enable_partials",
            "enable_entities",
            "max_delay",
            "diarization",
            "custom_vocabulary",
        }
    ),
    (TTSProviders, TTSProviders.ELEVENLABS.value): frozenset(
        {
            "model",
            "voice",
            "language",
            "sample_rate",
            "encoding",
            "speed",
            "stability",
            "similarity_boost",
            "style",
            "use_speaker_boost",
        }
    ),
    (TTSProviders, TTSProviders.AMAZON_POLLY.value): frozenset(
        {"region", "model", "voice", "language"}
    ),
    (TTSProviders, TTSProviders.CARTESIA.value): frozenset(
        {"model", "voice", "language", "sample_rate", "encoding", "speed"}
    ),
    (TTSProviders, TTSProviders.SARVAM.value): frozenset(
        {
            "model",
            "voice",
            "language",
            "sample_rate",
            "encoding",
            "pitch",
            "pace",
            "loudness",
            "temperature",
        }
    ),
    (TTSProviders, TTSProviders.OPENAI.value): frozenset({"model", "voice", "speed"}),
    (TTSProviders, TTSProviders.DEEPGRAM.value): frozenset(
        {"model", "sample_rate", "encoding", "container"}
    ),
    (TTSProviders, TTSProviders.GROQ.value): frozenset({"model", "voice", "sample_rate"}),
    (TTSProviders, TTSProviders.RIME.value): frozenset(
        {"model", "voice", "sample_rate", "audio_format"}
    ),
    (TTSProviders, TTSProviders.SMALLEST.value): frozenset(
        {"model", "voice", "language", "sample_rate", "add_wav_header"}
    ),
    (TTSProviders, TTSProviders.HUME.value): frozenset(
        {
            "model",
            "voice",
            "voice_description",
            "language",
            "speed",
            "format",
            "sample_rate",
            "instant_mode",
        }
    ),
    (TTSProviders, TTSProviders.MURF.value): frozenset(
        {
            "voice",
            "sample_rate",
            "format",
            "channel_type",
            "style",
            "rate",
            "pitch",
            "variation",
            "min_buffer_size",
            "max_buffer_delay_ms",
        }
    ),
}

_REQUIRED_CONFIG_FIELDS: dict[_ProviderKey, frozenset[str]] = {
    (RealtimeProviders, RealtimeProviders.AMAZON_NOVA_SONIC.value): frozenset(
        {
            "region",
            "model",
            "voice",
            "max_tokens",
            "temperature",
            "top_p",
            "endpointing_sensitivity",
        }
    ),
    (RealtimeProviders, RealtimeProviders.GEMINI_LIVE.value): frozenset(
        {"model", "voice"}
    ),
    (RealtimeProviders, RealtimeProviders.OPENAI_REALTIME.value): frozenset(
        {"model", "voice", "input_transcription_model"}
    ),
    (STTProviders, STTProviders.AMAZON_TRANSCRIBE.value): frozenset(
        {"region", "language"}
    ),
    (STTProviders, STTProviders.DEEPGRAM.value): frozenset({"model", "language"}),
    (STTProviders, STTProviders.DEEPGRAM_FLUX.value): frozenset({"model"}),
    (STTProviders, STTProviders.SARVAM.value): frozenset({"model", "language"}),
    (STTProviders, STTProviders.ASSEMBLYAI.value): frozenset({"model"}),
    (STTProviders, STTProviders.CARTESIA.value): frozenset({"model", "language"}),
    (STTProviders, STTProviders.GOOGLE.value): frozenset({"model", "language"}),
    (STTProviders, STTProviders.GLADIA.value): frozenset({"language"}),
    (STTProviders, STTProviders.REVAI.value): frozenset({"language"}),
    (STTProviders, STTProviders.SPEECHMATICS.value): frozenset({"language"}),
    (TTSProviders, TTSProviders.ELEVENLABS.value): frozenset({"model", "voice"}),
    (TTSProviders, TTSProviders.AMAZON_POLLY.value): frozenset(
        {"region", "model", "voice", "language"}
    ),
    (TTSProviders, TTSProviders.CARTESIA.value): frozenset({"model", "voice"}),
    (TTSProviders, TTSProviders.SARVAM.value): frozenset({"model", "voice", "language"}),
    (TTSProviders, TTSProviders.OPENAI.value): frozenset({"model", "voice"}),
    (TTSProviders, TTSProviders.DEEPGRAM.value): frozenset({"model"}),
    (TTSProviders, TTSProviders.GROQ.value): frozenset({"model", "voice"}),
    (TTSProviders, TTSProviders.RIME.value): frozenset({"model", "voice"}),
    (TTSProviders, TTSProviders.SMALLEST.value): frozenset({"model", "voice", "language"}),
    (TTSProviders, TTSProviders.HUME.value): frozenset({"model", "language"}),
    (TTSProviders, TTSProviders.MURF.value): frozenset({"voice"}),
}


class InvalidVoiceConfig(InvalidProviderConfig):
    """Raised when a voice provider config violates policy."""


@dataclass(frozen=True)
class VoiceProviderConfig:
    """Validated voice provider config with plaintext secrets held in memory only."""

    provider: VoiceProvider
    kind: VoiceKind
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        _validate_provider_kind(self.provider, self.kind)
        object.__setattr__(
            self,
            "config",
            _validate_config(self.config, self.provider),
        )
        object.__setattr__(
            self,
            "secrets",
            _validate_secrets(self.secrets, self.provider),
        )

    @classmethod
    def validate(
        cls,
        *,
        provider: str,
        kind: VoiceKind,
        config: Mapping[str, object] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> VoiceProviderConfig:
        return cls(
            provider=_parse_provider(provider, kind),
            kind=kind,
            config={} if config is None else config,
            secrets={} if secrets is None else secrets,
        )

    @property
    def secret(self) -> str | None:
        return self.secrets.get(_required_secret_field(self.provider))

    @property
    def capability(self) -> Capability:
        return Capability(self.kind.value)


def _parse_provider(provider: str, kind: VoiceKind) -> VoiceProvider:
    normalized = provider.lower().strip()
    try:
        if kind is VoiceKind.STT:
            return STTProviders(normalized)
        if kind is VoiceKind.TTS:
            return TTSProviders(normalized)
        if kind is VoiceKind.REALTIME:
            return RealtimeProviders(normalized)
    except ValueError:
        label = "realtime" if kind is VoiceKind.REALTIME else kind.value.upper()
        raise InvalidVoiceConfig(f"Unknown {label} provider: {provider}") from None
    raise InvalidVoiceConfig(f"Unknown voice kind: {kind}")


def _validate_provider_kind(provider: VoiceProvider, kind: VoiceKind) -> None:
    matches = (
        (kind is VoiceKind.STT and isinstance(provider, STTProviders))
        or (kind is VoiceKind.TTS and isinstance(provider, TTSProviders))
        or (kind is VoiceKind.REALTIME and isinstance(provider, RealtimeProviders))
    )
    if not matches:
        raise InvalidVoiceConfig(
            f"Provider {provider.value} does not match voice kind {kind.value}."
        )


def _validate_config(
    config: Mapping[str, object],
    provider: VoiceProvider,
) -> Mapping[str, object]:
    if not isinstance(config, Mapping):
        raise InvalidVoiceConfig("Config must be a mapping.")
    allowed = _allowed_config_fields(provider)
    unknown = set(config) - allowed
    if unknown:
        raise InvalidVoiceConfig(
            f"Unknown config fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [
        field_name
        for field_name in _required_config_fields(provider)
        if not _is_required_config_value(provider, field_name, config.get(field_name))
    ]
    if missing:
        raise InvalidVoiceConfig(
            f"Provider {provider.value} requires config fields: {missing}"
        )
    if provider is TTSProviders.HUME and not (
        _is_non_empty_string(config.get("voice"))
        or _is_non_empty_string(config.get("voice_description"))
    ):
        raise InvalidVoiceConfig(
            "Provider hume requires config field voice or voice_description."
        )
    normalized = dict(config)
    if provider in _AWS_PROVIDERS:
        normalized["region"] = _validate_aws_region(config["region"])
    if provider in {STTProviders.AMAZON_TRANSCRIBE, TTSProviders.AMAZON_POLLY}:
        normalized["language"] = _validate_language_code(config["language"])
    if provider is STTProviders.AMAZON_TRANSCRIBE:
        _validate_amazon_transcribe_config(normalized)
    elif provider is TTSProviders.AMAZON_POLLY:
        _validate_amazon_polly_config(normalized)
    elif isinstance(provider, RealtimeProviders):
        _validate_realtime_config(normalized, provider)
    return normalized


def _validate_secrets(
    secrets: Mapping[str, str],
    provider: VoiceProvider,
) -> Mapping[str, str]:
    if not isinstance(secrets, Mapping):
        raise InvalidVoiceConfig("Secrets must be a mapping.")
    allowed_fields = _allowed_secret_fields(provider)
    required_fields = _required_secret_fields(provider)
    unknown = set(secrets) - allowed_fields
    if unknown:
        raise InvalidVoiceConfig(
            f"Unknown secret fields for {provider.value}: {sorted(unknown)}"
        )
    missing = [
        field_name
        for field_name in required_fields
        if not _is_non_empty_string(secrets.get(field_name))
    ]
    invalid_optional = [
        field_name
        for field_name in set(secrets) - required_fields
        if not _is_non_empty_string(secrets.get(field_name))
    ]
    if missing:
        raise InvalidVoiceConfig(
            f"Provider {provider.value} requires non-empty secrets: {missing}"
        )
    if invalid_optional:
        raise InvalidVoiceConfig(
            f"Provider {provider.value} has empty optional secrets: "
            f"{invalid_optional}"
        )
    return dict(secrets)


def _allowed_config_fields(provider: VoiceProvider) -> frozenset[str]:
    return _CONFIG_FIELDS[(type(provider), provider.value)]


def _required_config_fields(
    provider: VoiceProvider,
) -> frozenset[str]:
    return _REQUIRED_CONFIG_FIELDS[(type(provider), provider.value)]


def _allowed_secret_fields(
    provider: VoiceProvider,
) -> frozenset[str]:
    if provider in _AWS_PROVIDERS:
        return _AWS_SECRET_FIELDS
    return frozenset({_required_secret_field(provider)})


def _required_secret_fields(
    provider: VoiceProvider,
) -> frozenset[str]:
    if provider in _AWS_PROVIDERS:
        return _AWS_REQUIRED_SECRET_FIELDS
    return frozenset({_required_secret_field(provider)})


def _required_secret_field(provider: VoiceProvider) -> str:
    if provider is STTProviders.GOOGLE:
        return _GOOGLE_SECRET_FIELD_NAME
    return _SECRET_FIELD_NAME


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_required_config_value(
    provider: VoiceProvider,
    field_name: str,
    value: object,
) -> bool:
    if provider is RealtimeProviders.AMAZON_NOVA_SONIC and field_name in {
        "max_tokens",
        "temperature",
        "top_p",
    }:
        return not isinstance(value, bool) and isinstance(value, (int, float))
    return _is_non_empty_string(value)


def _validate_aws_region(value: object) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) > 64 or not _AWS_REGION_PATTERN.fullmatch(normalized):
        raise InvalidVoiceConfig("region must be a valid AWS region identifier.")
    return normalized


def _validate_language_code(value: object) -> str:
    normalized = str(value).strip()
    if not _LANGUAGE_CODE_PATTERN.fullmatch(normalized):
        raise InvalidVoiceConfig(
            "language must be an ISO language code accepted by the provider."
        )
    return normalized


def _validate_amazon_transcribe_config(config: Mapping[str, object]) -> None:
    stability = config.get("partial_results_stability")
    if stability is not None and stability not in _PARTIAL_RESULTS_STABILITIES:
        raise InvalidVoiceConfig(
            "partial_results_stability must be low, medium, or high."
        )
    speaker_labels = config.get("show_speaker_label")
    if speaker_labels is not None and not isinstance(speaker_labels, bool):
        raise InvalidVoiceConfig("show_speaker_label must be a boolean.")
    for field_name in ("vocabulary_name", "language_model_name"):
        value = config.get(field_name)
        if value is not None and (
            not isinstance(value, str)
            or not _AWS_RESOURCE_NAME_PATTERN.fullmatch(value)
        ):
            raise InvalidVoiceConfig(
                f"{field_name} must be a valid AWS resource name."
            )


def _validate_amazon_polly_config(config: Mapping[str, object]) -> None:
    if config.get("model") not in _POLLY_ENGINES:
        raise InvalidVoiceConfig(
            "model must be standard, neural, long-form, or generative."
        )
    voice = config.get("voice")
    if not isinstance(voice, str) or not re.fullmatch(r"[0-9A-Za-z-]{1,50}", voice):
        raise InvalidVoiceConfig("voice must be a valid Amazon Polly voice ID.")


def _validate_realtime_config(
    config: Mapping[str, object],
    provider: RealtimeProviders,
) -> None:
    for field_name in ("model", "voice"):
        value = config.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise InvalidVoiceConfig(f"{field_name} must be a non-empty string.")

    if provider is RealtimeProviders.AMAZON_NOVA_SONIC:
        _validate_amazon_nova_sonic_config(config)
        return

    temperature = config.get("temperature")

    if provider is RealtimeProviders.GEMINI_LIVE:
        if temperature is not None and not _is_number_between(
            temperature, minimum=0, maximum=2
        ):
            raise InvalidVoiceConfig("temperature must be between 0 and 2.")
        compression = config.get("context_compression_enabled")
        if compression is not None and not isinstance(compression, bool):
            raise InvalidVoiceConfig(
                "context_compression_enabled must be a boolean."
            )
        trigger_tokens = config.get("context_compression_trigger_tokens")
        if trigger_tokens is not None and (
            isinstance(trigger_tokens, bool)
            or not isinstance(trigger_tokens, int)
            or trigger_tokens <= 0
        ):
            raise InvalidVoiceConfig(
                "context_compression_trigger_tokens must be a positive integer."
            )
        return

    if temperature is not None:
        raise InvalidVoiceConfig(
            "temperature is not supported by OpenAI Realtime."
        )

    transcription_model = config.get("input_transcription_model")
    if not isinstance(transcription_model, str) or not transcription_model.strip():
        raise InvalidVoiceConfig(
            "input_transcription_model must be a non-empty string."
        )
    vad_threshold = config.get("vad_threshold")
    if vad_threshold is not None and (
        isinstance(vad_threshold, bool)
        or not isinstance(vad_threshold, (int, float))
        or not 0 <= float(vad_threshold) <= 1
    ):
        raise InvalidVoiceConfig("vad_threshold must be between 0 and 1.")
    vad_silence_ms = config.get("vad_silence_ms")
    if vad_silence_ms is not None and (
        isinstance(vad_silence_ms, bool)
        or not isinstance(vad_silence_ms, int)
        or vad_silence_ms <= 0
    ):
        raise InvalidVoiceConfig("vad_silence_ms must be a positive integer.")


def _validate_amazon_nova_sonic_config(config: Mapping[str, object]) -> None:
    if config.get("model") not in AMAZON_NOVA_SONIC_MODELS:
        raise InvalidVoiceConfig(
            "model must be a supported Amazon Nova 2 Sonic model ID."
        )
    if config.get("voice") not in AMAZON_NOVA_SONIC_VOICES:
        raise InvalidVoiceConfig("voice must be a supported Amazon Nova 2 Sonic voice.")

    max_tokens = config.get("max_tokens")
    if (
        isinstance(max_tokens, bool)
        or not isinstance(max_tokens, int)
        or max_tokens <= 0
    ):
        raise InvalidVoiceConfig("max_tokens must be a positive integer.")
    if not _is_number_between(config.get("temperature"), minimum=0, maximum=1):
        raise InvalidVoiceConfig("temperature must be between 0 and 1.")
    if not _is_number_between(config.get("top_p"), minimum=0, maximum=1):
        raise InvalidVoiceConfig("top_p must be between 0 and 1.")
    if (
        config.get("endpointing_sensitivity")
        not in AMAZON_NOVA_SONIC_ENDPOINTING_SENSITIVITIES
    ):
        raise InvalidVoiceConfig(
            "endpointing_sensitivity must be HIGH, MEDIUM, or LOW."
        )


def _is_number_between(value: object, *, minimum: float, maximum: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and minimum <= float(value) <= maximum
    )


@dataclass(frozen=True)
class ResolvedSTT:
    """Immutable resolved STT runtime value with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: STTProviders
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False, compare=False)
    configured: bool = True
    verified: bool = False
    ready: bool = False
    granted: bool = False

    @classmethod
    def from_provider_config(
        cls,
        *,
        provider_config_id: UUID,
        organization_id: UUID,
        provider_config: EffectiveProviderConfig,
    ) -> ResolvedSTT:
        validated = VoiceProviderConfig.validate(
            provider=provider_config.provider,
            kind=VoiceKind.STT,
            config=provider_config.settings,
            secrets=provider_config.secrets,
        )
        if not isinstance(validated.provider, STTProviders):
            raise AssertionError("validated STT provider has the wrong kind")
        return cls(
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config.revision,
            organization_id=organization_id,
            provider=validated.provider,
            config=validated.config,
            secrets=validated.secrets,
            configured=provider_config.configured,
            verified=provider_config.verified,
            ready=provider_config.ready,
            granted=provider_config.granted,
        )

    @property
    def secret(self) -> str | None:
        return self.secrets.get(_required_secret_field(self.provider))


@dataclass(frozen=True)
class ResolvedTTS:
    """Immutable resolved TTS runtime value with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: TTSProviders
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False, compare=False)
    configured: bool = True
    verified: bool = False
    ready: bool = False
    granted: bool = False

    @classmethod
    def from_provider_config(
        cls,
        *,
        provider_config_id: UUID,
        organization_id: UUID,
        provider_config: EffectiveProviderConfig,
    ) -> ResolvedTTS:
        validated = VoiceProviderConfig.validate(
            provider=provider_config.provider,
            kind=VoiceKind.TTS,
            config=provider_config.settings,
            secrets=provider_config.secrets,
        )
        if not isinstance(validated.provider, TTSProviders):
            raise AssertionError("validated TTS provider has the wrong kind")
        return cls(
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config.revision,
            organization_id=organization_id,
            provider=validated.provider,
            config=validated.config,
            secrets=validated.secrets,
            configured=provider_config.configured,
            verified=provider_config.verified,
            ready=provider_config.ready,
            granted=provider_config.granted,
        )

    @property
    def secret(self) -> str | None:
        return self.secrets.get(_required_secret_field(self.provider))


@dataclass(frozen=True)
class ResolvedRealtime:
    """Immutable resolved realtime runtime value with plaintext credentials."""

    provider_config_id: UUID
    provider_config_revision: int
    organization_id: UUID
    provider: RealtimeProviders
    config: Mapping[str, object]
    secrets: Mapping[str, str] = field(repr=False, compare=False)
    configured: bool = True
    verified: bool = False
    ready: bool = False
    granted: bool = False

    @classmethod
    def from_provider_config(
        cls,
        *,
        provider_config_id: UUID,
        organization_id: UUID,
        provider_config: EffectiveProviderConfig,
    ) -> ResolvedRealtime:
        validated = VoiceProviderConfig.validate(
            provider=provider_config.provider,
            kind=VoiceKind.REALTIME,
            config=provider_config.settings,
            secrets=provider_config.secrets,
        )
        if not isinstance(validated.provider, RealtimeProviders):
            raise AssertionError("validated realtime provider has the wrong kind")
        return cls(
            provider_config_id=provider_config_id,
            provider_config_revision=provider_config.revision,
            organization_id=organization_id,
            provider=validated.provider,
            config=validated.config,
            secrets=validated.secrets,
            configured=provider_config.configured,
            verified=provider_config.verified,
            ready=provider_config.ready,
            granted=provider_config.granted,
        )

    @property
    def secret(self) -> str | None:
        return self.secrets.get("api_key")

    @property
    def provider_id(self) -> str:
        return self.provider.value
