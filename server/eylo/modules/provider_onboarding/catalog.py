"""Deterministic operator-facing catalog for provider configuration forms."""

from collections.abc import Iterable

from eylo.common.contracts.aws_catalog import AWS_REGION_OPTIONS
from eylo.common.contracts.llm_catalog import LLMProviders, models_for_provider
from eylo.modules.email_configs.catalog import EmailProviders
from eylo.modules.embedding_configs.catalog import (
    BEDROCK_EMBEDDING_DIMENSIONS,
    BEDROCK_EMBEDDING_MODELS,
    EmbeddingProviders,
)
from eylo.modules.memory_configs.catalog import MemoryProviders
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_onboarding.schemas import (
    CapabilityDefinition,
    ProviderDefinition,
    ProviderFieldCondition,
    ProviderFieldDefinition,
    ProviderFieldOption,
    ProviderOnboardingCatalogResponse,
)
from eylo.modules.reranking_configs.catalog import (
    BEDROCK_RERANKING_MODELS,
    RerankingProviders,
)
from eylo.modules.sandbox_configs.catalog import SandboxProviders
from eylo.modules.storage_configs.catalog import StorageProviders
from eylo.modules.telephony.provider_config_domain import TelephonyProvider
from eylo.modules.voice_configs.catalog import (
    AMAZON_NOVA_SONIC_ENDPOINTING_SENSITIVITIES,
    AMAZON_NOVA_SONIC_MODELS,
    AMAZON_NOVA_SONIC_VOICES,
    RealtimeProviders,
    STTProviders,
    TTSProviders,
    VoiceConfigFieldCatalog,
    VoiceKind,
    voice_config_field_catalog,
)
from eylo.modules.webrtc_configs.catalog import WebRTCProviders

_FIELD_LABELS = {
    "access_key_id": "Access key ID",
    "add_wav_header": "Add WAV header",
    "alternative_languages": "Alternative languages",
    "api_host": "API host",
    "api_key": "API key",
    "api_secret": "API secret",
    "api_token": "API token",
    "application_id": "Application ID",
    "app_name": "Metered domain",
    "auth_id": "Auth ID",
    "auth_token": "Auth token",
    "base_url": "Base URL",
    "buffer_size_seconds": "Buffer size (seconds)",
    "channel_type": "Channel type",
    "context_compression_enabled": "Context compression",
    "context_compression_trigger_tokens": "Compression trigger tokens",
    "client_ip": "Client IP",
    "command_timeout_seconds": "Command timeout (seconds)",
    "cpu_cores": "CPU cores",
    "default_from_email": "Default from email",
    "default_from_name": "Default from name",
    "detect_language": "Detect language",
    "disk_mb": "Disk limit (MB)",
    "embedding_provider_config_id": "Embedding configuration",
    "enable_entities": "Enable entities",
    "enable_partials": "Enable partial transcripts",
    "eot_threshold": "End-of-turn threshold",
    "eot_timeout_ms": "End-of-turn timeout (ms)",
    "endpointing_sensitivity": "Endpointing sensitivity",
    "fixed_region": "Fixed region",
    "flush_signal": "Send flush signal",
    "high_vad_sensitivity": "High VAD sensitivity",
    "input_audio_codec": "Input audio codec",
    "instant_mode": "Instant mode",
    "input_transcription_model": "Input transcription model",
    "interim_results": "Interim results",
    "keyterms_prompt": "Key terms",
    "llm_provider_config_id": "LLM configuration",
    "max_buffer_delay_ms": "Maximum buffer delay (ms)",
    "max_output_bytes": "Maximum output (bytes)",
    "max_retries": "Maximum retries",
    "max_sessions": "Maximum concurrent sessions",
    "max_tokens": "Maximum output tokens",
    "memory_mb": "Memory limit (MB)",
    "min_buffer_size": "Minimum buffer size",
    "preferred_region": "Preferred region",
    "partial_results_stability": "Partial transcript stability",
    "private_key": "Private key",
    "profanity_filter": "Profanity filter",
    "receiver_client": "Receiver client",
    "retry_delay": "Retry delay (seconds)",
    "region": "AWS region",
    "sample_rate": "Sample rate",
    "secret_access_key": "Secret access key",
    "service_account_json": "Service account JSON",
    "session_token": "Session token",
    "show_speaker_label": "Speaker labels",
    "signature_secret": "Signature secret",
    "similarity_boost": "Similarity boost",
    "smtp_host": "SMTP host",
    "smtp_password": "SMTP password",
    "smtp_port": "SMTP port",
    "smtp_security": "SMTP security",
    "smtp_username": "SMTP username",
    "stop_sequences": "Stop sequences",
    "ttl_seconds": "Session lifetime (seconds)",
    "top_p": "Top P",
    "use_speaker_boost": "Use speaker boost",
    "utterance_end_ms": "Utterance end delay (ms)",
    "vad_events": "VAD events",
    "vad_silence_ms": "VAD silence duration (ms)",
    "vad_threshold": "VAD threshold",
    "voice_description": "Voice description",
    "webhook_base_url": "Webhook base URL",
    "language_model_name": "Custom language model",
    "vocabulary_name": "Custom vocabulary",
}

_FIELD_DESCRIPTIONS = {
    "base_url": (
        "Optional exact endpoint approved by this deployment. The server rejects "
        "URLs outside its allowlist."
    ),
    "embedding_provider_config_id": (
        "Ready embedding configuration used by this memory backend."
    ),
    "llm_provider_config_id": "Ready LLM configuration used by this memory backend.",
    "region": "AWS region where the service and selected model are available.",
    "network": "Docker V1 requires network access to be disabled.",
    "private_key": "PEM-encoded private key. Stored encrypted and never returned.",
    "service_account_json": (
        "Google service-account JSON. Stored encrypted and never returned."
    ),
    "webhook_base_url": "Public HTTPS origin or path used for provider callbacks.",
}

_VOICE_BOOLEAN_FIELDS = frozenset(
    {
        "add_wav_header",
        "detect_language",
        "diarization",
        "enable_entities",
        "enable_partials",
        "flush_signal",
        "high_vad_sensitivity",
        "instant_mode",
        "interim_results",
        "context_compression_enabled",
        "profanity_filter",
        "punctuate",
        "punctuation",
        "show_speaker_label",
        "use_speaker_boost",
        "vad_events",
    }
)
_VOICE_INTEGER_FIELDS = frozenset(
    {
        "buffer_size_seconds",
        "eot_timeout_ms",
        "context_compression_trigger_tokens",
        "max_buffer_delay_ms",
        "min_buffer_size",
        "sample_rate",
        "utterance_end_ms",
        "variation",
    }
)
_VOICE_NUMBER_FIELDS = frozenset(
    {
        "eot_threshold",
        "loudness",
        "max_delay",
        "pace",
        "pitch",
        "rate",
        "similarity_boost",
        "speed",
        "stability",
        "temperature",
        "vad_silence_ms",
        "vad_threshold",
    }
)
_VOICE_LIST_FIELDS = frozenset(
    {"alternative_languages", "custom_vocabulary", "keyterms_prompt"}
)


def get_provider_onboarding_catalog() -> ProviderOnboardingCatalogResponse:
    """Return the complete, deterministic provider-onboarding projection."""
    return ProviderOnboardingCatalogResponse(
        capabilities=(
            _llm_capability(),
            _stt_capability(),
            _tts_capability(),
            _realtime_capability(),
            _webrtc_capability(),
            _telephony_capability(),
            _email_capability(),
            _storage_capability(),
            _embedding_capability(),
            _reranking_capability(),
            _memory_capability(),
            _sandbox_capability(),
        )
    )


def _llm_capability() -> CapabilityDefinition:
    providers = []
    for provider in LLMProviders:
        fields = [
            _field(
                "model",
                kind="select",
                required=True,
                options=_options(models_for_provider(provider)),
            ),
            _field(
                "max_tokens",
                kind="integer",
                required=provider
                in (LLMProviders.ANTHROPIC, LLMProviders.BEDROCK),
                minimum=1,
            ),
            _field("temperature", kind="number", minimum=0, maximum=2),
        ]
        if provider in (
            LLMProviders.ANTHROPIC,
            LLMProviders.BEDROCK,
            LLMProviders.GEMINI,
        ):
            fields.append(_field("top_k", kind="integer", minimum=1))
        fields.append(_field("top_p", kind="number", minimum=0, maximum=1))
        if provider is not LLMProviders.OPENAI_RESPONSES:
            fields.append(_field("stop_sequences", kind="string_list"))
        if provider is LLMProviders.BEDROCK:
            fields.extend(
                (
                    _aws_region_field(required=True),
                    _secret("access_key_id", required=True),
                    _secret("secret_access_key", required=True),
                    _secret("session_token"),
                )
            )
        else:
            fields.append(_secret("api_key", required=True))
        providers.append(
            _provider(
                provider.value.lower(),
                _provider_label(provider.value),
                fields,
            )
        )
    return _capability(
        Capability.LLM,
        "Language models",
        "Models used by Agent reasoning and generation.",
        "/api/llm-configs",
        providers,
    )


def _stt_capability() -> CapabilityDefinition:
    specs = {
        STTProviders.AMAZON_TRANSCRIBE: (
            (
                "region",
                "language",
                "partial_results_stability",
                "vocabulary_name",
                "language_model_name",
                "show_speaker_label",
            ),
            {"region", "language"},
        ),
        STTProviders.DEEPGRAM: (
            (
                "model",
                "language",
                "sample_rate",
                "encoding",
                "interim_results",
                "punctuate",
                "vad_events",
                "endpointing",
                "utterance_end_ms",
            ),
            {"model", "language"},
        ),
        STTProviders.DEEPGRAM_FLUX: (
            (
                "model",
                "sample_rate",
                "encoding",
                "eot_threshold",
                "eot_timeout_ms",
                "high_vad_sensitivity",
            ),
            {"model"},
        ),
        STTProviders.SARVAM: (
            (
                "model",
                "language",
                "mode",
                "sample_rate",
                "encoding",
                "input_audio_codec",
                "high_vad_sensitivity",
                "flush_signal",
            ),
            {"model", "language"},
        ),
        STTProviders.ASSEMBLYAI: (
            (
                "model",
                "sample_rate",
                "encoding",
                "eot_threshold",
                "eot_timeout_ms",
                "keyterms_prompt",
            ),
            {"model"},
        ),
        STTProviders.CARTESIA: (
            ("model", "language", "sample_rate", "encoding"),
            {"model", "language"},
        ),
        STTProviders.GOOGLE: (
            (
                "model",
                "language",
                "sample_rate",
                "interim_results",
                "punctuation",
                "profanity_filter",
                "detect_language",
                "alternative_languages",
            ),
            {"model", "language"},
        ),
        STTProviders.GLADIA: (
            ("language", "sample_rate", "encoding", "buffer_size_seconds"),
            {"language"},
        ),
        STTProviders.REVAI: (("language", "sample_rate"), {"language"}),
        STTProviders.SPEECHMATICS: (
            (
                "language",
                "sample_rate",
                "enable_partials",
                "enable_entities",
                "max_delay",
                "diarization",
                "custom_vocabulary",
            ),
            {"language"},
        ),
    }
    providers = []
    for provider, (fields, required) in specs.items():
        if provider is STTProviders.AMAZON_TRANSCRIBE:
            providers.append(
                _amazon_voice_provider(
                    VoiceKind.STT,
                    provider.value,
                    _provider_label(provider.value),
                    fields,
                    required,
                )
            )
            continue
        providers.append(
            _voice_provider(
                VoiceKind.STT,
                provider.value,
                _provider_label(provider.value),
                fields,
                required,
                secret_key=(
                    "service_account_json"
                    if provider is STTProviders.GOOGLE
                    else "api_key"
                ),
            )
        )
    return _capability(
        Capability.STT,
        "Speech to text",
        "Streaming transcription providers used by voice Agents.",
        "/api/stt-configs",
        providers,
    )


def _tts_capability() -> CapabilityDefinition:
    specs = {
        TTSProviders.AMAZON_POLLY: (
            ("region", "model", "voice", "language"),
            {"region", "model", "voice", "language"},
        ),
        TTSProviders.ELEVENLABS: (
            (
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
            ),
            {"model", "voice"},
        ),
        TTSProviders.CARTESIA: (
            ("model", "voice", "language", "sample_rate", "encoding", "speed"),
            {"model", "voice"},
        ),
        TTSProviders.SARVAM: (
            (
                "model",
                "voice",
                "language",
                "sample_rate",
                "encoding",
                "pitch",
                "pace",
                "loudness",
                "temperature",
            ),
            {"model", "voice", "language"},
        ),
        TTSProviders.OPENAI: (
            ("model", "voice", "speed"),
            {"model", "voice"},
        ),
        TTSProviders.DEEPGRAM: (
            ("model", "sample_rate", "encoding", "container"),
            {"model"},
        ),
        TTSProviders.GROQ: (
            ("model", "voice", "sample_rate"),
            {"model", "voice"},
        ),
        TTSProviders.RIME: (
            ("model", "voice", "sample_rate", "audio_format"),
            {"model", "voice"},
        ),
        TTSProviders.SMALLEST: (
            ("model", "voice", "language", "sample_rate", "add_wav_header"),
            {"model", "voice", "language"},
        ),
        TTSProviders.HUME: (
            (
                "model",
                "voice",
                "voice_description",
                "language",
                "speed",
                "format",
                "sample_rate",
                "instant_mode",
            ),
            {"model", "language"},
        ),
        TTSProviders.MURF: (
            (
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
            ),
            {"voice"},
        ),
    }
    providers = []
    for provider, (fields, required) in specs.items():
        if provider is TTSProviders.AMAZON_POLLY:
            providers.append(
                _amazon_voice_provider(
                    VoiceKind.TTS,
                    provider.value,
                    _provider_label(provider.value),
                    fields,
                    required,
                )
            )
            continue
        require_one_of = (("voice", "voice_description"),) if provider is TTSProviders.HUME else ()
        providers.append(
            _voice_provider(
                VoiceKind.TTS,
                provider.value,
                _provider_label(provider.value),
                fields,
                required,
                secret_key="api_key",
                require_one_of=require_one_of,
            )
        )
    return _capability(
        Capability.TTS,
        "Text to speech",
        "Speech synthesis providers used by voice Agents.",
        "/api/tts-configs",
        providers,
    )


def _realtime_capability() -> CapabilityDefinition:
    providers = (
        _provider(
            RealtimeProviders.AMAZON_NOVA_SONIC.value,
            "AWS Amazon Nova 2 Sonic",
            (
                _voice_config_field(
                    VoiceKind.REALTIME,
                    RealtimeProviders.AMAZON_NOVA_SONIC.value,
                    "region",
                    required=True,
                ),
                _field(
                    "model",
                    kind="select",
                    required=True,
                    options=_options(AMAZON_NOVA_SONIC_MODELS),
                ),
                _field(
                    "voice",
                    kind="select",
                    required=True,
                    options=_options(AMAZON_NOVA_SONIC_VOICES),
                ),
                _field("max_tokens", kind="integer", required=True, minimum=1),
                _field(
                    "temperature",
                    kind="number",
                    required=True,
                    minimum=0,
                    maximum=1,
                ),
                _field(
                    "top_p",
                    kind="number",
                    required=True,
                    minimum=0,
                    maximum=1,
                ),
                _field(
                    "endpointing_sensitivity",
                    kind="select",
                    required=True,
                    options=_options(
                        AMAZON_NOVA_SONIC_ENDPOINTING_SENSITIVITIES
                    ),
                ),
                _secret("access_key_id", required=True),
                _secret("secret_access_key", required=True),
                _secret("session_token"),
            ),
            description=(
                "Native speech-to-speech sessions through Amazon Bedrock Runtime."
            ),
        ),
        _provider(
            RealtimeProviders.GEMINI_LIVE.value,
            "Google Gemini Live",
            (
                _voice_config_field(
                    VoiceKind.REALTIME,
                    RealtimeProviders.GEMINI_LIVE.value,
                    "model",
                    required=True,
                ),
                _voice_config_field(
                    VoiceKind.REALTIME,
                    RealtimeProviders.GEMINI_LIVE.value,
                    "voice",
                    required=True,
                ),
                _field("temperature", kind="number", minimum=0, maximum=2),
                _field("context_compression_enabled", kind="boolean"),
                _field(
                    "context_compression_trigger_tokens",
                    kind="integer",
                    minimum=1,
                ),
                _secret("api_key", required=True),
            ),
        ),
        _provider(
            RealtimeProviders.OPENAI_REALTIME.value,
            "OpenAI Realtime",
            (
                _voice_config_field(
                    VoiceKind.REALTIME,
                    RealtimeProviders.OPENAI_REALTIME.value,
                    "model",
                    required=True,
                ),
                _voice_config_field(
                    VoiceKind.REALTIME,
                    RealtimeProviders.OPENAI_REALTIME.value,
                    "voice",
                    required=True,
                ),
                _voice_config_field(
                    VoiceKind.REALTIME,
                    RealtimeProviders.OPENAI_REALTIME.value,
                    "input_transcription_model",
                    required=True,
                    description=(
                        "OpenAI transcription model used for user speech transcripts."
                    ),
                ),
                _field("vad_threshold", kind="number", minimum=0, maximum=1),
                _field("vad_silence_ms", kind="integer", minimum=1),
                _secret("api_key", required=True),
            ),
        ),
    )
    return _capability(
        Capability.REALTIME,
        "Realtime speech",
        "Speech-to-speech model sessions used by realtime voice Agents.",
        "/api/realtime-configs",
        providers,
    )


def _webrtc_capability() -> CapabilityDefinition:
    common = (
        _field(
            "timeout",
            kind="number",
            minimum=0,
            maximum=30,
            description="Request timeout greater than 0 and at most 30 seconds.",
        ),
        _field("max_retries", kind="integer", minimum=0, maximum=5),
        _field("retry_delay", kind="number", minimum=0, maximum=10),
    )
    metered = _provider(
        WebRTCProviders.METERED.value,
        "Metered",
        (
            _field(
                "app_name",
                required=True,
                description=(
                    "Paste the Metered Domain shown in the dashboard, such as "
                    "your_app.metered.live. The app name alone is also accepted."
                ),
            ),
            *common,
            _secret("api_key", required=True),
        ),
    )
    turnix = _provider(
        WebRTCProviders.TURNIX.value,
        "Turnix",
        (
            _field("initiator_client"),
            _field("receiver_client"),
            _field("room"),
            _field("ttl", kind="integer", minimum=1, maximum=86_400),
            _field("preferred_region"),
            _field("fixed_region"),
            _field("client_ip"),
            *common,
            _secret("api_key", required=True),
        ),
    )
    return _capability(
        Capability.WEBRTC,
        "Realtime transport",
        "TURN credentials and realtime connectivity for browser voice sessions.",
        "/api/webrtc-configs",
        (metered, turnix),
    )


def _telephony_capability() -> CapabilityDefinition:
    providers = (
        _provider(
            TelephonyProvider.TWILIO.value,
            "Twilio",
            (
                _field("webhook_base_url", required=True),
                _secret("account_sid", required=True),
                _secret("auth_token", required=True),
            ),
        ),
        _provider(
            TelephonyProvider.PLIVO.value,
            "Plivo",
            (
                _field("webhook_base_url", required=True),
                _secret("auth_id", required=True),
                _secret("auth_token", required=True),
            ),
        ),
        _provider(
            TelephonyProvider.VONAGE.value,
            "Vonage",
            (
                _field("webhook_base_url", required=True),
                _field("application_id", required=True),
                _secret("api_key", required=True),
                _secret("api_secret", required=True),
                _secret("private_key", required=True, multiline=True),
                _secret("signature_secret", required=True),
            ),
        ),
        _provider(
            TelephonyProvider.EXOTEL.value,
            "Exotel",
            (
                _field("webhook_base_url", required=True),
                _field("application_id", required=True),
                _field("api_host", required=True),
                _secret("api_key", required=True),
                _secret("api_token", required=True),
                _secret("account_sid", required=True),
            ),
        ),
    )
    return _capability(
        Capability.TELEPHONY,
        "Telephony",
        "Carrier accounts used for inbound and outbound phone calls.",
        "/api/telephony-configs",
        providers,
    )


def _email_capability() -> CapabilityDefinition:
    common = (
        _field("default_from_email", required=True),
        _field("default_from_name", required=True),
        _field(
            "timeout",
            kind="number",
            required=True,
            minimum=0,
            maximum=60,
            description="Request timeout greater than 0 and at most 60 seconds.",
        ),
    )
    providers = (
        _provider(
            EmailProviders.SMTP.value,
            "SMTP",
            (
                *common,
                _field("smtp_host", required=True),
                _field(
                    "smtp_port", kind="integer", required=True, minimum=1, maximum=65_535
                ),
                _field("smtp_username", required=True),
                _field(
                    "smtp_security",
                    kind="select",
                    required=True,
                    options=(
                        _option("implicit_tls", "Implicit TLS"),
                        _option("starttls", "STARTTLS"),
                    ),
                ),
                _secret("smtp_password", required=True),
            ),
        ),
        _provider(
            EmailProviders.SENDGRID.value,
            "SendGrid",
            (*common, _secret("api_key", required=True)),
        ),
    )
    return _capability(
        Capability.EMAIL,
        "Email",
        "Email delivery providers used by Agents and products.",
        "/api/email-configs",
        providers,
    )


def _storage_capability() -> CapabilityDefinition:
    credential_mode = _field(
        "credential_mode",
        kind="select",
        required=True,
        options=(
            _option("static", "Static credentials"),
            _option("session", "Temporary session credentials"),
        ),
    )
    session_condition = ProviderFieldCondition(
        field="credential_mode",
        equals="session",
    )
    providers = (
        _provider(
            StorageProviders.S3.value,
            "Amazon S3",
            (
                _field("bucket", required=True),
                _aws_region_field(required=True),
                credential_mode,
                _secret("access_key_id", required=True),
                _secret("secret_access_key", required=True),
                _secret(
                    "session_token",
                    visible_when=session_condition,
                    required_when=session_condition,
                ),
            ),
        ),
        _provider(
            StorageProviders.FILESYSTEM.value,
            "Local filesystem",
            (
                _field(
                    "namespace",
                    required=True,
                    description=(
                        "Isolated storage namespace using letters, numbers, dot, "
                        "underscore, or hyphen."
                    ),
                ),
            ),
        ),
    )
    return _capability(
        Capability.STORAGE,
        "Object storage",
        "Durable storage for recordings and generated artifacts.",
        "/api/storage-configs",
        providers,
    )


def _embedding_capability() -> CapabilityDefinition:
    providers = (
        _provider(
            EmbeddingProviders.BEDROCK.value,
            "AWS Bedrock",
            (
                _field(
                    "model",
                    kind="select",
                    required=True,
                    options=_options(BEDROCK_EMBEDDING_MODELS),
                ),
                _aws_region_field(
                    required=True,
                    description="AWS region where Bedrock Runtime serves the model.",
                ),
                _field(
                    "dimensions",
                    kind="integer",
                    required=True,
                    minimum=min(BEDROCK_EMBEDDING_DIMENSIONS),
                    maximum=max(BEDROCK_EMBEDDING_DIMENSIONS),
                    description="Titan V2 supports exactly 256, 512, or 1024.",
                ),
                _field(
                    "normalize",
                    kind="boolean",
                    required=True,
                    description="Ask Titan V2 to normalize every returned vector.",
                ),
                _secret("access_key_id", required=True),
                _secret("secret_access_key", required=True),
                _secret("session_token"),
            ),
            description="Amazon Titan Text Embeddings V2 through Bedrock Runtime.",
        ),
        _provider(
            EmbeddingProviders.OPENAI.value,
            "OpenAI-compatible",
            (
                _field("model", required=True),
                _field("base_url"),
                _secret("api_key", required=True),
            ),
            description="OpenAI plus deployment-approved compatible endpoints.",
        ),
        _provider(
            EmbeddingProviders.VOYAGE.value,
            "Voyage AI",
            (_field("model", required=True), _secret("api_key", required=True)),
        ),
    )
    return _capability(
        Capability.EMBEDDING,
        "Embeddings",
        "Vector embedding providers used by knowledge and memory.",
        "/api/embedding-configs",
        providers,
    )


def _reranking_capability() -> CapabilityDefinition:
    providers = (
        _provider(
            RerankingProviders.BEDROCK.value,
            "AWS Bedrock",
            (
                _field(
                    "model",
                    kind="select",
                    required=True,
                    options=_options(BEDROCK_RERANKING_MODELS),
                ),
                _aws_region_field(
                    required=True,
                    description=(
                        "AWS region serving the selected reranker. Supported "
                        "model-region pairs are checked on save; access is checked "
                        "only when you verify."
                    ),
                ),
                _secret("access_key_id", required=True),
                _secret("secret_access_key", required=True),
                _secret("session_token"),
            ),
            description="Amazon or Cohere reranking through Bedrock Agent Runtime.",
        ),
        _provider(
            RerankingProviders.COHERE.value,
            "Cohere",
            (
                _field("model", required=True),
                _field("base_url"),
                _secret("api_key", required=True),
            ),
        ),
        _provider(
            RerankingProviders.VOYAGE.value,
            "Voyage AI",
            (_field("model", required=True), _secret("api_key", required=True)),
        ),
    )
    return _capability(
        Capability.RERANKING,
        "Reranking",
        "Search rerankers used to improve knowledge retrieval quality.",
        "/api/reranking-configs",
        providers,
    )


def _memory_capability() -> CapabilityDefinition:
    provider = _provider(
        MemoryProviders.PGVECTOR.value,
        "PostgreSQL + pgvector",
        (
            _field(
                "embedding_provider_config_id",
                kind="provider_config",
                required=True,
                reference_capability=Capability.EMBEDDING,
            ),
            _field(
                "llm_provider_config_id",
                kind="provider_config",
                required=True,
                reference_capability=Capability.LLM,
            ),
        ),
    )
    return _capability(
        Capability.MEMORY,
        "Memory",
        "Long-term Agent memory backed by explicit LLM and embedding configs.",
        "/api/memory-configs",
        (provider,),
    )


def _sandbox_capability() -> CapabilityDefinition:
    provider = _provider(
        SandboxProviders.DOCKER.value,
        "Docker",
        (
            _field(
                "endpoint",
                required=True,
                description="Absolute local Docker Unix socket, for example unix:///var/run/docker.sock.",
            ),
            _field("image", required=True),
            _field(
                "memory_mb",
                wire_key="memoryMb",
                kind="integer",
                required=True,
                minimum=64,
                maximum=16_384,
            ),
            _field(
                "cpu_cores",
                wire_key="cpuCores",
                kind="number",
                required=True,
                minimum=0,
                maximum=8,
                description="CPU limit greater than 0 and at most 8 cores.",
            ),
            _field(
                "disk_mb",
                wire_key="diskMb",
                kind="integer",
                required=True,
                minimum=64,
                maximum=16_384,
            ),
            _field("pids", kind="integer", required=True, minimum=8, maximum=4_096),
            _field(
                "ttl_seconds",
                wire_key="ttlSeconds",
                kind="integer",
                required=True,
                minimum=60,
                maximum=86_400,
            ),
            _field(
                "command_timeout_seconds",
                wire_key="commandTimeoutSeconds",
                kind="integer",
                required=True,
                minimum=1,
                maximum=3_600,
            ),
            _field(
                "max_output_bytes",
                wire_key="maxOutputBytes",
                kind="integer",
                required=True,
                minimum=1_024,
                maximum=10 * 1_024 * 1_024,
            ),
            _field(
                "max_sessions",
                wire_key="maxSessions",
                kind="integer",
                required=True,
                minimum=1,
                maximum=100,
            ),
            _field("network", kind="boolean", required=True),
        ),
    )
    return _capability(
        Capability.SANDBOX,
        "Sandbox",
        "Isolated execution capacity for Agent commands and durable work.",
        "/api/sandbox-configs",
        (provider,),
    )


def _voice_provider(
    kind: VoiceKind,
    provider_id: str,
    label: str,
    config_fields: tuple[str, ...],
    required_fields: set[str],
    *,
    secret_key: str,
    require_one_of: tuple[tuple[str, ...], ...] = (),
) -> ProviderDefinition:
    fields = [
        _voice_config_field(
            kind,
            provider_id,
            key,
            required=key in required_fields,
        )
        for key in config_fields
    ]
    fields.append(
        _secret(
            secret_key,
            required=True,
            multiline=secret_key == "service_account_json",
        )
    )
    return _provider(
        provider_id,
        label,
        fields,
        require_one_of=require_one_of,
    )


def _amazon_voice_provider(
    kind: VoiceKind,
    provider_id: str,
    label: str,
    config_fields: tuple[str, ...],
    required_fields: set[str],
) -> ProviderDefinition:
    fields = []
    for key in config_fields:
        if key == "partial_results_stability":
            fields.append(
                _field(
                    key,
                    kind="select",
                    options=_options(("low", "medium", "high")),
                )
            )
        else:
            fields.append(
                _voice_config_field(
                    kind,
                    provider_id,
                    key,
                    required=key in required_fields,
                )
            )
    fields.extend(
        (
            _secret("access_key_id", required=True),
            _secret("secret_access_key", required=True),
            _secret("session_token"),
        )
    )
    return _provider(provider_id, label, fields)


def _voice_config_field(
    kind: VoiceKind,
    provider_id: str,
    key: str,
    *,
    required: bool = False,
    description: str | None = None,
) -> ProviderFieldDefinition:
    catalog = voice_config_field_catalog(kind, provider_id, key)
    if catalog is None:
        return _field(
            key,
            kind=_voice_field_kind(key),
            required=required,
            description=description,
        )
    return _field(
        key,
        kind="select",
        required=required,
        options=_voice_catalog_options(catalog),
        allow_custom=catalog.allow_custom,
        description=description,
    )


def _voice_catalog_options(
    catalog: VoiceConfigFieldCatalog,
) -> tuple[ProviderFieldOption, ...]:
    return tuple(_option(item.value, item.label) for item in catalog.options)


def _aws_region_field(
    *,
    required: bool = False,
    description: str | None = None,
) -> ProviderFieldDefinition:
    """Build the common searchable AWS Region field used by every capability."""
    return _field(
        "region",
        kind="select",
        required=required,
        options=tuple(_option(value, label) for value, label in AWS_REGION_OPTIONS),
        allow_custom=True,
        description=description,
    )


def _voice_field_kind(key: str) -> str:
    if key in _VOICE_BOOLEAN_FIELDS:
        return "boolean"
    if key in _VOICE_INTEGER_FIELDS:
        return "integer"
    if key in _VOICE_NUMBER_FIELDS:
        return "number"
    if key in _VOICE_LIST_FIELDS:
        return "string_list"
    return "text"


def _capability(
    capability: Capability,
    label: str,
    description: str,
    configure_via: str,
    providers: Iterable[ProviderDefinition],
) -> CapabilityDefinition:
    return CapabilityDefinition(
        capability=capability,
        label=label,
        description=description,
        configure_via=configure_via,
        providers=tuple(providers),
    )


def _provider(
    provider_id: str,
    label: str,
    fields: Iterable[ProviderFieldDefinition],
    *,
    description: str | None = None,
    require_one_of: tuple[tuple[str, ...], ...] = (),
) -> ProviderDefinition:
    return ProviderDefinition(
        id=provider_id,
        label=label,
        description=description,
        fields=tuple(fields),
        require_one_of=require_one_of,
    )


def _field(
    key: str,
    *,
    wire_key: str | None = None,
    kind: str = "text",
    required: bool = False,
    options: tuple[ProviderFieldOption, ...] = (),
    allow_custom: bool = False,
    minimum: float | None = None,
    maximum: float | None = None,
    description: str | None = None,
    visible_when: ProviderFieldCondition | None = None,
    required_when: ProviderFieldCondition | None = None,
    reference_capability: Capability | None = None,
) -> ProviderFieldDefinition:
    return ProviderFieldDefinition(
        key=key,
        wire_key=wire_key or key,
        label=_field_label(key),
        description=description or _FIELD_DESCRIPTIONS.get(key),
        kind=kind,
        required=required,
        options=options,
        allow_custom=allow_custom,
        minimum=minimum,
        maximum=maximum,
        visible_when=visible_when,
        required_when=required_when,
        reference_capability=reference_capability,
    )


def _secret(
    key: str,
    *,
    required: bool = False,
    multiline: bool = False,
    visible_when: ProviderFieldCondition | None = None,
    required_when: ProviderFieldCondition | None = None,
) -> ProviderFieldDefinition:
    return ProviderFieldDefinition(
        key=key,
        wire_key=key,
        label=_field_label(key),
        description=_FIELD_DESCRIPTIONS.get(key),
        kind="password",
        target="secrets",
        required=required,
        secret=True,
        multiline=multiline,
        visible_when=visible_when,
        required_when=required_when,
    )


def _options(values: Iterable[str]) -> tuple[ProviderFieldOption, ...]:
    return tuple(_option(value, value) for value in values)


def _option(value: str, label: str) -> ProviderFieldOption:
    return ProviderFieldOption(value=value, label=label)


def _field_label(key: str) -> str:
    return _FIELD_LABELS.get(key, key.replace("_", " ").capitalize())


def _provider_label(provider: str) -> str:
    labels = {
        "ANTHROPIC": "Anthropic",
        "BEDROCK": "AWS Bedrock",
        "CEREBRAS": "Cerebras",
        "GEMINI": "Google Gemini",
        "GROQ": "Groq",
        "OPENAI": "OpenAI",
        "OPENAI_RESPONSES": "OpenAI Responses",
        "SARVAM": "Sarvam",
        "assemblyai": "AssemblyAI",
        "amazon-polly": "Amazon Polly",
        "amazon-transcribe": "Amazon Transcribe",
        "deepgram": "Deepgram",
        "deepgram-flux": "Deepgram Flux",
        "elevenlabs": "ElevenLabs",
        "google": "Google Cloud",
        "gladia": "Gladia",
        "groq": "Groq",
        "hume": "Hume",
        "murf": "Murf",
        "openai": "OpenAI",
        "revai": "Rev AI",
        "rime": "Rime",
        "sarvam": "Sarvam",
        "smallest": "Smallest AI",
        "speechmatics": "Speechmatics",
        "cartesia": "Cartesia",
    }
    return labels.get(provider, provider.replace("-", " ").title())


__all__ = ["get_provider_onboarding_catalog"]
