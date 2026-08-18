import type {
  VoiceConfigDefinitionInput,
  VoiceConfigDefinitionOutput,
  VoiceConfigFormValues,
  VoiceConfigRecord,
  VoiceInterruptionType,
  VoiceRuntimeMode,
} from "@/features/voice/voice.types";

const DEFAULT_VOICE_CONFIG_VALUES: VoiceConfigFormValues = {
  acknowledgementPhrases: "",
  audioStorageEnabled: false,
  backoffSeconds: 0,
  description: "",
  endCallAfterSilenceMs: 0,
  endCallMessage: "",
  endCallPhrases: "",
  firstMessage: "",
  firstMessageMode: "assistant-speaks-first",
  interruptionPhrases: "",
  interruptionSensitivity: 0.5,
  interruptionType: "transcript",
  maxDurationSeconds: 0,
  metricsEnabled: true,
  name: "",
  numWords: 0,
  realtimeProviderConfigId: null,
  recordingConsentMessage:
    "This call is recorded for quality and training purposes.",
  recordingConsentRequired: true,
  redactPiiInLogs: true,
  redactPiiInTranscripts: true,
  reminderMaxCount: 2,
  reminderMessages: "Are you still there?",
  reminderTriggerMs: 10_000,
  runtimeMode: "decomposed",
  startResponsiveness: 0.5,
  startWaitMs: 0,
  storageProviderConfigId: null,
  sttProviderConfigId: null,
  transcriptStorageEnabled: true,
  ttsProviderConfigId: null,
  vendorLatencyTrackingEnabled: true,
};

const DEFAULT_ARTIFACTS: NonNullable<VoiceConfigDefinitionOutput["artifacts"]> =
  {
    audio_storage_enabled: false,
    transcript_storage_enabled: true,
  };
const DEFAULT_COMPLIANCE: NonNullable<
  VoiceConfigDefinitionOutput["compliance"]
> = {
  allow_sensitive_metadata: false,
  recording_consent_message:
    "This call is recorded for quality and training purposes.",
  recording_consent_required: true,
  redact_pii_in_logs: true,
  redact_pii_in_transcripts: true,
  store_raw_vendor_payloads: false,
};
const DEFAULT_CONVERSATION_CONTROL: NonNullable<
  VoiceConfigDefinitionOutput["conversation_control"]
> = {
  end_call_phrases: [] as string[],
  first_message_interruptible: false,
  first_message_mode: "assistant-speaks-first" as const,
  max_duration_seconds: 0,
};
const DEFAULT_OBSERVABILITY: NonNullable<
  VoiceConfigDefinitionOutput["observability"]
> = {
  debug_events_enabled: false,
  metrics_enabled: true,
  vendor_latency_tracking_enabled: true,
};
const DEFAULT_SILENCE: NonNullable<VoiceConfigDefinitionOutput["silence"]> = {
  end_call_after_silence_ms: 0,
  reminder_max_count: 2,
  reminder_messages: ["Are you still there?"],
  reminder_trigger_ms: 10_000,
};
const DEFAULT_START_SPEAKING: NonNullable<
  VoiceConfigDefinitionOutput["start_speaking_plan"]
> = {
  begin_message_delay_ms: 0,
  responsiveness: 0.5,
  wait_ms: 0,
};
const DEFAULT_STOP_SPEAKING: NonNullable<
  VoiceConfigDefinitionOutput["stop_speaking_plan"]
> = {
  acknowledgement_phrases: [] as string[],
  backoff_seconds: 0,
  interruption_phrases: [] as string[],
  interruption_sensitivity: 0.5,
  interruption_type: "transcript" as const,
  num_words: 0,
  voice_seconds: 0,
};

function freshVoiceConfigValues(): VoiceConfigFormValues {
  return { ...DEFAULT_VOICE_CONFIG_VALUES };
}

function valuesFromVoiceConfig(
  record: VoiceConfigRecord,
): VoiceConfigFormValues {
  const definition = record.config;
  const conversation =
    definition.conversation_control ?? DEFAULT_CONVERSATION_CONTROL;
  const start = definition.start_speaking_plan ?? DEFAULT_START_SPEAKING;
  const stop = definition.stop_speaking_plan ?? DEFAULT_STOP_SPEAKING;
  const silence = definition.silence ?? DEFAULT_SILENCE;
  const compliance = definition.compliance ?? DEFAULT_COMPLIANCE;
  const artifacts = definition.artifacts ?? DEFAULT_ARTIFACTS;
  const observability = definition.observability ?? DEFAULT_OBSERVABILITY;

  return {
    acknowledgementPhrases: joinLines(stop.acknowledgement_phrases),
    audioStorageEnabled: artifacts.audio_storage_enabled,
    backoffSeconds: stop.backoff_seconds,
    description: record.description ?? "",
    endCallAfterSilenceMs: silence.end_call_after_silence_ms,
    endCallMessage: conversation.end_call_message ?? "",
    endCallPhrases: joinLines(conversation.end_call_phrases),
    firstMessage: conversation.first_message ?? "",
    firstMessageMode: conversation.first_message_mode,
    interruptionPhrases: joinLines(stop.interruption_phrases),
    interruptionSensitivity: stop.interruption_sensitivity,
    interruptionType: stop.interruption_type,
    maxDurationSeconds: conversation.max_duration_seconds,
    metricsEnabled: observability.metrics_enabled,
    name: record.name,
    numWords: stop.num_words,
    realtimeProviderConfigId: definition.realtime_provider_config_id ?? null,
    recordingConsentMessage: compliance.recording_consent_message,
    recordingConsentRequired: compliance.recording_consent_required,
    redactPiiInLogs: compliance.redact_pii_in_logs,
    redactPiiInTranscripts: compliance.redact_pii_in_transcripts,
    reminderMaxCount: silence.reminder_max_count,
    reminderMessages: joinLines(silence.reminder_messages),
    reminderTriggerMs: silence.reminder_trigger_ms,
    runtimeMode:
      definition.realtime_provider_config_id === null ||
      definition.realtime_provider_config_id === undefined
        ? "decomposed"
        : "realtime",
    startResponsiveness: start.responsiveness,
    startWaitMs: start.wait_ms,
    storageProviderConfigId: definition.storage_provider_config_id ?? null,
    sttProviderConfigId: definition.stt_provider_config_id ?? null,
    transcriptStorageEnabled: artifacts.transcript_storage_enabled,
    ttsProviderConfigId: definition.tts_provider_config_id ?? null,
    vendorLatencyTrackingEnabled: observability.vendor_latency_tracking_enabled,
  };
}

function definitionFromValues(
  base: VoiceConfigDefinitionOutput | null,
  values: VoiceConfigFormValues,
): VoiceConfigDefinitionInput {
  const existing = (base ?? {
    schema_version: "voice-agent-config.v1",
  }) as VoiceConfigDefinitionInput;
  const silence = {
    ...(existing.silence ?? DEFAULT_SILENCE),
    end_call_after_silence_ms: values.endCallAfterSilenceMs,
    reminder_max_count: values.reminderMaxCount,
    reminder_messages: splitLines(values.reminderMessages),
    reminder_trigger_ms: values.reminderTriggerMs,
  };

  return {
    ...existing,
    artifacts: {
      ...(existing.artifacts ?? DEFAULT_ARTIFACTS),
      audio_storage_enabled: values.audioStorageEnabled,
      transcript_storage_enabled: values.transcriptStorageEnabled,
    },
    capabilities: null,
    compliance: {
      ...(existing.compliance ?? DEFAULT_COMPLIANCE),
      recording_consent_message: values.recordingConsentMessage.trim(),
      recording_consent_required: values.recordingConsentRequired,
      redact_pii_in_logs: values.redactPiiInLogs,
      redact_pii_in_transcripts: values.redactPiiInTranscripts,
    },
    conversation_control: {
      ...(existing.conversation_control ?? DEFAULT_CONVERSATION_CONTROL),
      end_call_message: normalizeOptionalText(values.endCallMessage),
      end_call_phrases: splitLines(values.endCallPhrases),
      first_message: normalizeOptionalText(values.firstMessage),
      first_message_mode: values.firstMessageMode,
      max_duration_seconds: values.maxDurationSeconds,
    },
    observability: {
      ...(existing.observability ?? DEFAULT_OBSERVABILITY),
      metrics_enabled: values.metricsEnabled,
      vendor_latency_tracking_enabled: values.vendorLatencyTrackingEnabled,
    },
    realtime_provider_config_id:
      values.runtimeMode === "realtime"
        ? values.realtimeProviderConfigId
        : null,
    silence,
    schema_version: existing.schema_version ?? "voice-agent-config.v1",
    start_speaking_plan: {
      ...(existing.start_speaking_plan ?? DEFAULT_START_SPEAKING),
      responsiveness: values.startResponsiveness,
      wait_ms: values.startWaitMs,
    },
    stop_speaking_plan: {
      ...(existing.stop_speaking_plan ?? DEFAULT_STOP_SPEAKING),
      acknowledgement_phrases: splitLines(values.acknowledgementPhrases),
      backoff_seconds: values.backoffSeconds,
      interruption_phrases: splitLines(values.interruptionPhrases),
      interruption_sensitivity: values.interruptionSensitivity,
      interruption_type: values.interruptionType,
      num_words: values.numWords,
    },
    storage_provider_config_id: values.storageProviderConfigId,
    stt_provider_config_id: values.sttProviderConfigId,
    tts_provider_config_id: values.ttsProviderConfigId,
  };
}

function validateVoiceConfigValues(
  values: VoiceConfigFormValues,
): string | null {
  if (values.name.trim() === "") {
    return "Name is required.";
  }
  if (values.name.trim().length > 128) {
    return "Name must be 128 characters or fewer.";
  }
  if (values.description.length > 2_000) {
    return "Description must be 2,000 characters or fewer.";
  }
  if (
    values.recordingConsentRequired &&
    values.recordingConsentMessage.trim() === ""
  ) {
    return "A recording notification is required when notification is enabled.";
  }
  if (
    values.reminderMaxCount > 0 &&
    splitLines(values.reminderMessages).length === 0
  ) {
    return "Add at least one silence reminder or set maximum reminders to 0.";
  }
  return null;
}

function runtimeReadinessMessage(values: VoiceConfigFormValues): string | null {
  if (values.runtimeMode === "decomposed") {
    if (
      values.sttProviderConfigId === null ||
      values.ttsProviderConfigId === null
    ) {
      return "Select both STT and TTS before publishing a bound Agent.";
    }
  } else if (values.realtimeProviderConfigId === null) {
    return "Select a Realtime provider before publishing a bound Agent.";
  }
  if (values.audioStorageEnabled && values.storageProviderConfigId === null) {
    return "Select Storage before publishing with recording uploads enabled.";
  }
  return null;
}

function parseVoiceConfigFormValues(
  value: unknown,
): VoiceConfigFormValues | null {
  if (!isRecord(value)) {
    return null;
  }
  const runtimeMode = parseRuntimeMode(value.runtimeMode);
  const interruptionType = parseInterruptionType(value.interruptionType);
  const firstMessageMode =
    value.firstMessageMode === "assistant-speaks-first" ||
    value.firstMessageMode === "assistant-waits"
      ? value.firstMessageMode
      : null;
  if (
    runtimeMode === null ||
    interruptionType === null ||
    firstMessageMode === null
  ) {
    return null;
  }

  const parsed = {
    acknowledgementPhrases: parseText(value.acknowledgementPhrases, 20_000),
    audioStorageEnabled: parseBoolean(value.audioStorageEnabled),
    backoffSeconds: parseNumber(value.backoffSeconds, 0, 10),
    description: parseText(value.description, 2_000),
    endCallAfterSilenceMs: parseInteger(
      value.endCallAfterSilenceMs,
      0,
      3_600_000,
    ),
    endCallMessage: parseText(value.endCallMessage, 20_000),
    endCallPhrases: parseText(value.endCallPhrases, 20_000),
    firstMessage: parseText(value.firstMessage, 20_000),
    firstMessageMode,
    interruptionPhrases: parseText(value.interruptionPhrases, 20_000),
    interruptionSensitivity: parseNumber(value.interruptionSensitivity, 0, 1),
    interruptionType,
    maxDurationSeconds: parseInteger(value.maxDurationSeconds, 0, 86_400),
    metricsEnabled: parseBoolean(value.metricsEnabled),
    name: parseText(value.name, 128),
    numWords: parseInteger(value.numWords, 0, 50),
    realtimeProviderConfigId: parseNullableText(
      value.realtimeProviderConfigId,
      100,
    ),
    recordingConsentMessage: parseText(value.recordingConsentMessage, 1_000),
    recordingConsentRequired: parseBoolean(value.recordingConsentRequired),
    redactPiiInLogs: parseBoolean(value.redactPiiInLogs),
    redactPiiInTranscripts: parseBoolean(value.redactPiiInTranscripts),
    reminderMaxCount: parseInteger(value.reminderMaxCount, 0, 10),
    reminderMessages: parseText(value.reminderMessages, 20_000),
    reminderTriggerMs: parseInteger(value.reminderTriggerMs, 1_000, 300_000),
    runtimeMode,
    startResponsiveness: parseNumber(value.startResponsiveness, 0, 1),
    startWaitMs: parseInteger(value.startWaitMs, 0, 5_000),
    storageProviderConfigId: parseNullableText(
      value.storageProviderConfigId,
      100,
    ),
    sttProviderConfigId: parseNullableText(value.sttProviderConfigId, 100),
    transcriptStorageEnabled: parseBoolean(value.transcriptStorageEnabled),
    ttsProviderConfigId: parseNullableText(value.ttsProviderConfigId, 100),
    vendorLatencyTrackingEnabled: parseBoolean(
      value.vendorLatencyTrackingEnabled,
    ),
  };
  if (Object.values(parsed).some((item) => item === undefined)) {
    return null;
  }
  return parsed as VoiceConfigFormValues;
}

function joinLines(values: readonly string[] | undefined): string {
  return (values ?? []).join("\n");
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
}

function normalizeOptionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
}

function parseRuntimeMode(value: unknown): VoiceRuntimeMode | null {
  return value === "decomposed" || value === "realtime" ? value : null;
}

function parseInterruptionType(value: unknown): VoiceInterruptionType | null {
  return value === "transcript" || value === "vad" ? value : null;
}

function parseText(value: unknown, maximum: number): string | undefined {
  return typeof value === "string" && value.length <= maximum
    ? value
    : undefined;
}

function parseNullableText(
  value: unknown,
  maximum: number,
): string | null | undefined {
  if (value === null) {
    return null;
  }
  return typeof value === "string" && value.length <= maximum
    ? value
    : undefined;
}

function parseBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function parseInteger(
  value: unknown,
  minimum: number,
  maximum: number,
): number | undefined {
  return Number.isSafeInteger(value) &&
    Number(value) >= minimum &&
    Number(value) <= maximum
    ? Number(value)
    : undefined;
}

function parseNumber(
  value: unknown,
  minimum: number,
  maximum: number,
): number | undefined {
  return typeof value === "number" &&
    Number.isFinite(value) &&
    value >= minimum &&
    value <= maximum
    ? value
    : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export {
  DEFAULT_VOICE_CONFIG_VALUES,
  definitionFromValues,
  freshVoiceConfigValues,
  parseVoiceConfigFormValues,
  runtimeReadinessMessage,
  validateVoiceConfigValues,
  valuesFromVoiceConfig,
};
