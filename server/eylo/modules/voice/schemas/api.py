"""Data contracts for the `voice` domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from eylo.common.contracts.voice import InterruptionType as InterruptionType


def experimental(default: object, **kwargs: object) -> Any:
    """Mark a field as stored but not yet acted on at runtime.

    Setting one of these has no effect. The marker is deliberately visible in
    two places: the description reaches the generated API docs, so an operator
    reading them is told before they rely on it, and `json_schema_extra` is
    machine-readable so callers can identify an unwired field.

    Razor R2 forbids configuration that does nothing. A field may be inert only
    while it is explicitly marked; remove the marker when the runtime lands.
    """
    description = (
        "EXPERIMENTAL — stored but not yet enforced. Setting this has no "
        "effect on behaviour."
    )
    if "default_factory" in kwargs:
        # Pydantic rejects default and default_factory together; the factory
        # wins and `default` is ignored, so it must not be passed on.
        return Field(
            description=description, json_schema_extra={"experimental": True}, **kwargs
        )
    return Field(
        default=default,
        description=description,
        json_schema_extra={"experimental": True},
        **kwargs,
    )


class StopSpeakingPlan(BaseModel):
    interruption_type: InterruptionType = Field(
        default=InterruptionType.TRANSCRIPT,
        description="Type of interruption.",
    )
    num_words: int = Field(
        default=0,
        ge=0,
        le=50,
        description="Minimum word count before allowing interruption. 0 = interrupt on any speech.",
    )
    voice_seconds: float = experimental(
        0.0,
        ge=0.0,
        le=10.0,
    )
    backoff_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Cooldown period after an interruption before allowing another.",
    )
    interruption_sensitivity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized interruption sensitivity. Higher values interrupt more eagerly.",
    )
    acknowledgement_phrases: list[str] = Field(default_factory=list)
    interruption_phrases: list[str] = Field(default_factory=list)


class StartSpeakingPlan(BaseModel):
    wait_ms: int = Field(
        default=0,
        description="Number of milliseconds to wait before starting to speak.",
        ge=0,
        le=5000,
    )
    responsiveness: float = Field(default=0.5, ge=0.0, le=1.0)
    begin_message_delay_ms: int = experimental(0, ge=0, le=30000)


class AmbientNoiseConfig(BaseModel):
    """Controls comfort noise played while the agent is thinking."""

    enabled: bool = Field(
        default=True,
        description="Enable ambient comfort noise during agent thinking.",
    )
    amplitude: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Noise amplitude in int16 scale (0=silent, 50=subtle, 500=noticeable).",
    )


class FillerConfig(BaseModel):
    """Controls filler phrase injection during LLM thinking gaps."""

    enabled: bool = Field(default=True, description="Enable filler phrase injection.")
    phrases: list[str] = Field(
        default_factory=lambda: [
            "Let me look into that.",
            "One moment.",
            "Let me check.",
            "Just a moment.",
            "Let me think about that.",
            "Give me a second.",
        ],
        description="Filler phrases to randomly choose from.",
    )
    delay_ms: int = Field(
        default=3000,
        ge=100,
        le=3000,
        description="Milliseconds to wait before injecting a filler phrase.",
    )


class ConversationControl(BaseModel):
    """Top-level conversation behavior settings."""

    first_message: str | None = Field(
        default=None,
        description="Greeting text the agent speaks at the start of the session.",
    )
    first_message_mode: Literal["assistant-speaks-first", "assistant-waits"] = Field(
        default="assistant-speaks-first",
        description="Whether the agent speaks first or waits for the user.",
    )
    first_message_interruptible: bool = experimental(False)
    max_duration_seconds: int = Field(
        default=0,
        ge=0,
        le=86400,
        description="Maximum call duration in seconds. 0 = unlimited.",
    )
    end_call_message: str | None = Field(
        default=None,
        description="Message to play before ending the call (on timeout or end-call phrase).",
    )
    end_call_phrases: list[str] = Field(
        default_factory=list,
        description="Phrases that trigger call termination when spoken by the user.",
    )


class SilenceConfig(BaseModel):
    """Silence detection and response behavior."""

    reminder_trigger_ms: int = Field(
        default=10000,
        ge=1000,
        le=300000,
        description="Milliseconds of silence before a reminder is spoken.",
    )
    reminder_max_count: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Maximum number of reminders before ending the call.",
    )
    reminder_messages: list[str] = Field(
        default_factory=lambda: ["Are you still there?"],
        description="Messages to use as silence reminders (cycled in order).",
    )
    end_call_after_silence_ms: int = Field(
        default=0,
        ge=0,
        le=3_600_000,
        description="End call after this many ms of total silence. 0 = disabled.",
    )


class BackgroundAudioConfig(BaseModel):
    ambient_noise: AmbientNoiseConfig = Field(default_factory=AmbientNoiseConfig)
    filler: FillerConfig = Field(default_factory=FillerConfig)
    # Stored parity contract. Wire denoising into the voice pipeline or vendor
    # socket adapter when a runtime can actually request noise cancellation.
    denoising_mode: Literal["off", "noise-cancellation"] = experimental("off")


class BackchannelConfig(BaseModel):
    # Backchannels acknowledge a caller while the caller is still speaking.
    # They are not filler phrases, which occupy an Agent thinking gap.
    enabled: bool = experimental(False)
    frequency: float = experimental(0.2, ge=0.0, le=1.0)
    words: list[str] = experimental(
        None,
        default_factory=lambda: ["uh-huh", "I see", "right"],
    )


class CompliancePlan(BaseModel):
    # Every field here is enforced.
    #
    # The two redaction flags are pattern-based: they find personal data that
    # has a shape and not personal data that does not. See eylo.common.redaction
    # for what that covers, and do not read them as a compliance guarantee.
    #
    # recording_consent_required enables notification delivery and visible
    # notification state. It is not affirmative opt-in and never gates the
    # primary recording flow. Post-call policy owns later data controls.
    recording_consent_required: bool = True
    recording_consent_message: str = Field(
        default=("This call is recorded for quality and training purposes."),
        min_length=1,
        max_length=1000,
        description=(
            "Notification attempted before the greeting when "
            "recording_consent_required is set. Delivery state is visible, but "
            "notification failure or decline does not interrupt recording."
        ),
    )
    redact_pii_in_transcripts: bool = True
    redact_pii_in_logs: bool = True
    store_raw_vendor_payloads: bool = False
    allow_sensitive_metadata: bool = False


class ArtifactPlan(BaseModel):
    # Storage is explicit. Artifact deletion happens only through an
    # organization-requested deletion workflow. Recording access is served
    # through authenticated application routes, not provider URLs.
    transcript_storage_enabled: bool = True
    audio_storage_enabled: bool = False


class ObservabilityPlan(BaseModel):
    # metrics_enabled and vendor_latency_tracking_enabled are enforced in
    # pipelines/voice/browser.py::_collect_audio_metrics. debug_events_enabled
    # is not: there is no debug event stream to gate, and inventing one to
    # satisfy the field would be the wrong way round.
    metrics_enabled: bool = True
    debug_events_enabled: bool = experimental(False)
    vendor_latency_tracking_enabled: bool = True


class KeypadInputPlan(BaseModel):
    """Per-agent keypad behaviour."""

    enabled: bool = experimental(False)
    digit_limit: int = experimental(6, ge=1, le=32)
    termination_key: str = experimental("#")
    timeout_ms: int = experimental(5000, ge=1000, le=60000)


class TransportConfig(BaseModel):
    browser_transport: Literal["webrtc", "websocket"] = experimental("webrtc")
    telephony_provider: str | None = experimental(None)
    ring_duration_ms: int = experimental(30000, ge=1000, le=300000)
    keypad_input: KeypadInputPlan = Field(default_factory=KeypadInputPlan)


class HookConfig(BaseModel):
    # Lifecycle hooks are persisted but not run by the voice config module. A
    # voice lifecycle hook runner should consume this section from pipeline events.
    name: str = experimental(...)
    enabled: bool = experimental(True)
    event: str = experimental(...)
    url: str | None = experimental(None)
    headers: dict[str, str] = experimental(None, default_factory=dict)


class ServerConfig(BaseModel):
    # Webhook callback settings are stored ahead of runtime use. Delivery should
    # be owned by a voice lifecycle webhook publisher/listener.
    webhook_url: str | None = experimental(None)
    webhook_events: list[str] = experimental(None, default_factory=list)
    webhook_timeout_ms: int = experimental(30000, ge=1000, le=120000)
    headers: dict[str, str] = experimental(None, default_factory=dict)


class FallbackChainsConfig(BaseModel):
    # Fallback enablement is a runtime factory/pipeline concern. The config
    # service only validates and stores the contract.
    stt_enabled: bool = experimental(False)
    tts_enabled: bool = experimental(False)
    realtime_enabled: bool = experimental(False)


class CapabilityWarning(BaseModel):
    section: str
    field: str
    message: str


class VoiceRuntimeCapabilities(BaseModel):
    warnings: list[CapabilityWarning] = Field(default_factory=list)


class VoicePlatformFeatureRead(BaseModel):
    """One provider-independent behavior implemented by Eylo's voice pipeline."""

    key: str
    label: str
    enabled: bool
    description: str
    provider_independent: Literal[True] = True


class VoiceProviderCapabilityRead(BaseModel):
    """Native behavior declared by one selected provider adapter."""

    kind: Literal["stt", "tts", "realtime"]
    provider_config_id: UUID
    provider: str
    ready: bool
    native_capabilities: dict[str, Any]


class VoiceConfigCompatibilityRead(BaseModel):
    """Provider/platform capability separation for one Voice Config."""

    voice_config_id: UUID
    voice_config_revision: int = Field(gt=0)
    platform_features: list[VoicePlatformFeatureRead]
    selected_providers: list[VoiceProviderCapabilityRead]
    guidance: str


class VoiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stt_provider_config_id: UUID | None = None
    stt_provider_config_revision: int | None = Field(default=None, gt=0)
    tts_provider_config_id: UUID | None = None
    tts_provider_config_revision: int | None = Field(default=None, gt=0)
    realtime_provider_config_id: UUID | None = None
    realtime_provider_config_revision: int | None = Field(default=None, gt=0)
    storage_provider_config_id: UUID | None = None
    storage_provider_config_revision: int | None = Field(default=None, gt=0)
    conversation_control: ConversationControl = Field(
        default_factory=ConversationControl
    )

    start_speaking_plan: StartSpeakingPlan = Field(default_factory=StartSpeakingPlan)
    stop_speaking_plan: StopSpeakingPlan = Field(default_factory=StopSpeakingPlan)
    silence: SilenceConfig = Field(default_factory=SilenceConfig)
    backchannel: BackchannelConfig = Field(default_factory=BackchannelConfig)
    compliance: CompliancePlan = Field(default_factory=CompliancePlan)
    artifacts: ArtifactPlan = Field(default_factory=ArtifactPlan)
    observability: ObservabilityPlan = Field(default_factory=ObservabilityPlan)
    background_audio: BackgroundAudioConfig = Field(
        default_factory=BackgroundAudioConfig
    )
    transport: TransportConfig = Field(default_factory=TransportConfig)
    hooks: list[HookConfig] = Field(default_factory=list)
    server: ServerConfig = Field(default_factory=ServerConfig)
    fallback_chains: FallbackChainsConfig = Field(default_factory=FallbackChainsConfig)
    capabilities: VoiceRuntimeCapabilities | None = None
    schema_version: str = "voice-agent-config.v1"

class OrganizationVoiceConfigCreate(BaseModel):
    """Create one reusable organization-owned Voice Config."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2_000)
    config: VoiceConfig

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Voice Config name cannot be blank.")
        return normalized


class OrganizationVoiceConfigUpdate(BaseModel):
    """Optimistically update the current Voice Config definition."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2_000)
    config: VoiceConfig | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Voice Config name cannot be blank.")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> OrganizationVoiceConfigUpdate:
        if not ({"name", "description", "config"} & self.model_fields_set):
            raise ValueError("Voice Config update must include a change.")
        return self


class VoiceConfigRead(BaseModel):
    """Current editable Voice Config definition."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    revision: int = Field(gt=0)
    config: VoiceConfig
    created_at: datetime
    updated_at: datetime


VOICE_CONFIG_SECTION_SCHEMAS: dict[str, type[BaseModel] | type[list[HookConfig]]] = {
    "conversation_control": ConversationControl,
    "start_speaking_plan": StartSpeakingPlan,
    "stop_speaking_plan": StopSpeakingPlan,
    "silence": SilenceConfig,
    "backchannel": BackchannelConfig,
    "compliance": CompliancePlan,
    "artifacts": ArtifactPlan,
    "observability": ObservabilityPlan,
    "background_audio": BackgroundAudioConfig,
    "transport": TransportConfig,
    "server": ServerConfig,
    "fallback_chains": FallbackChainsConfig,
}

VOICE_CONFIG_LIST_SECTIONS = {"hooks"}


def validate_voice_config_section(section: str, data: Any) -> Any:
    """Validate a section payload and return the typed section value."""
    if section in VOICE_CONFIG_LIST_SECTIONS:
        if not isinstance(data, list):
            raise ValueError(f"Voice config section '{section}' must be a list.")
        return [HookConfig.model_validate(item) for item in data]

    schema = VOICE_CONFIG_SECTION_SCHEMAS.get(section)
    if schema is None:
        valid_sections = sorted(
            [*VOICE_CONFIG_SECTION_SCHEMAS.keys(), *VOICE_CONFIG_LIST_SECTIONS]
        )
        raise ValueError(
            f"Unknown voice config section '{section}'. Expected one of: {', '.join(valid_sections)}."
        )
    return schema.model_validate(data)
