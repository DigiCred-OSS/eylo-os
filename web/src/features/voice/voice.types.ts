import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type VoiceConfigRecord = components["schemas"]["VoiceConfigRead"];
type VoiceConfigDefinitionInput = components["schemas"]["VoiceConfig-Input"];
type VoiceConfigDefinitionOutput = components["schemas"]["VoiceConfig-Output"];
type VoiceConfigCompatibility =
  components["schemas"]["VoiceConfigCompatibilityRead"];
type VoiceConfigCreateInput =
  components["schemas"]["OrganizationVoiceConfigCreate"];
type VoiceConfigUpdateInput =
  components["schemas"]["OrganizationVoiceConfigUpdate"];
type VoiceInterruptionType = components["schemas"]["InterruptionType"];

type VoiceRuntimeMode = "decomposed" | "realtime";
type VoiceConfigFormMode = "create" | "edit";
type VoiceConfigFormSection =
  | "identity"
  | "runtime"
  | "conversation"
  | "interaction"
  | "data"
  | "observability";

interface VoiceConfigFormValues {
  acknowledgementPhrases: string;
  audioStorageEnabled: boolean;
  backoffSeconds: number;
  description: string;
  endCallAfterSilenceMs: number;
  endCallMessage: string;
  endCallPhrases: string;
  firstMessage: string;
  firstMessageMode: "assistant-speaks-first" | "assistant-waits";
  interruptionPhrases: string;
  interruptionSensitivity: number;
  interruptionType: VoiceInterruptionType;
  maxDurationSeconds: number;
  metricsEnabled: boolean;
  name: string;
  numWords: number;
  realtimeProviderConfigId: string | null;
  recordingConsentMessage: string;
  recordingConsentRequired: boolean;
  redactPiiInLogs: boolean;
  redactPiiInTranscripts: boolean;
  reminderMaxCount: number;
  reminderMessages: string;
  reminderTriggerMs: number;
  runtimeMode: VoiceRuntimeMode;
  startResponsiveness: number;
  startWaitMs: number;
  storageProviderConfigId: string | null;
  sttProviderConfigId: string | null;
  transcriptStorageEnabled: boolean;
  ttsProviderConfigId: string | null;
  vendorLatencyTrackingEnabled: boolean;
}

interface VoiceConfigDraftContext {
  memberKey: string;
  mode: VoiceConfigFormMode;
  organizationId: string;
  voiceConfigId: string | null;
}

interface StoredVoiceConfigDraft {
  baseRevision: number | null;
  savedAt: string;
  values: VoiceConfigFormValues;
  version: 1;
}

type VoiceFilterProperty = "audio_storage" | "runtime";
type VoiceSortDirection = "asc" | "desc";
type VoiceSortField = "name" | "revision" | "updated_at";

interface VoiceCollectionQuery {
  direction: VoiceSortDirection;
  filters: FilterGroup<VoiceFilterProperty>;
  search: string;
  sortBy: VoiceSortField;
}

export type {
  StoredVoiceConfigDraft,
  VoiceCollectionQuery,
  VoiceConfigCompatibility,
  VoiceConfigCreateInput,
  VoiceConfigDefinitionInput,
  VoiceConfigDefinitionOutput,
  VoiceConfigDraftContext,
  VoiceConfigFormMode,
  VoiceConfigFormSection,
  VoiceConfigFormValues,
  VoiceConfigRecord,
  VoiceConfigUpdateInput,
  VoiceFilterProperty,
  VoiceInterruptionType,
  VoiceRuntimeMode,
  VoiceSortDirection,
  VoiceSortField,
};
