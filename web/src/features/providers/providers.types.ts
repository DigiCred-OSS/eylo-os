import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type ProviderCapability = components["schemas"]["Capability"];
type ProviderCapabilities = components["schemas"]["CapabilitiesResponse"];
type ProviderCapabilityStatus =
  components["schemas"]["CapabilityStatusResponse"];
type ProviderCatalog =
  components["schemas"]["ProviderOnboardingCatalogResponse"];
type ProviderCapabilityDefinition =
  components["schemas"]["CapabilityDefinition"];
type ProviderDefinition = components["schemas"]["ProviderDefinition"];
type ProviderFieldDefinition = components["schemas"]["ProviderFieldDefinition"];
type ProviderTool = components["schemas"]["ToolResponseSchema"];
type ProviderFieldValue = string | number | boolean | string[] | null;

type ProviderConfigResponse =
  | components["schemas"]["LLMConfigResponse"]
  | components["schemas"]["VoiceConfigResponse"]
  | components["schemas"]["WebRTCConfigResponse"]
  | components["schemas"]["ProviderConfigApiResponseSchema"]
  | components["schemas"]["EmailConfigResponse"]
  | components["schemas"]["StorageConfigResponse"]
  | components["schemas"]["EmbeddingConfigResponse"]
  | components["schemas"]["RerankingConfigResponse"]
  | components["schemas"]["MemoryConfigResponse"]
  | components["schemas"]["SandboxConfigResponse"];

type ProviderConfigCreateInput =
  | components["schemas"]["LLMConfigCreate"]
  | components["schemas"]["VoiceConfigCreate"]
  | components["schemas"]["WebRTCConfigCreate"]
  | components["schemas"]["ProviderConfigCreateSchema"]
  | components["schemas"]["EmailConfigCreate"]
  | components["schemas"]["StorageConfigCreate"]
  | components["schemas"]["EmbeddingConfigCreate"]
  | components["schemas"]["RerankingConfigCreate"]
  | components["schemas"]["MemoryConfigCreate"]
  | components["schemas"]["SandboxConfigCreate"];

type ProviderConfigUpdateInput =
  | components["schemas"]["LLMConfigUpdate"]
  | components["schemas"]["VoiceConfigUpdate"]
  | components["schemas"]["WebRTCConfigUpdate"]
  | components["schemas"]["ProviderConfigUpdateSchema"]
  | components["schemas"]["EmailConfigUpdate"]
  | components["schemas"]["StorageConfigUpdate"]
  | components["schemas"]["EmbeddingConfigUpdate"]
  | components["schemas"]["RerankingConfigUpdate"]
  | components["schemas"]["MemoryConfigUpdate"]
  | components["schemas"]["SandboxConfigUpdate"];

interface ProviderConfigRecord {
  capability: ProviderCapability;
  config: Record<string, unknown>;
  configured: boolean;
  enabled: boolean;
  id: string;
  name: string;
  provider: string;
  raw: ProviderConfigResponse;
  ready: boolean;
  revision: number;
  secrets: Record<string, string>;
  verified: boolean;
  verifiedAt: string | null;
}

type ProviderReferenceField =
  | "emailProviderConfigId"
  | "fileUploadEmbeddingProviderConfigId"
  | "llmProviderConfigId"
  | "memoryProviderConfigId"
  | "realtimeProviderConfigId"
  | "rerankingProviderConfigId"
  | "storageProviderConfigId"
  | "sttProviderConfigId"
  | "ttsProviderConfigId"
  | "webrtcProviderConfigId";

interface ProviderReferenceOption {
  description: string;
  id: string;
  isSelectable: boolean;
  label: string;
  provider: string;
  status: string;
}

type ProviderFilterProperty = "enabled" | "provider" | "ready" | "verified";
type ProviderSortDirection = "asc" | "desc";
type ProviderSortField = "name" | "provider" | "ready" | "verified_at";

interface ProviderCollectionQuery {
  direction: ProviderSortDirection;
  filters: FilterGroup<ProviderFilterProperty>;
  search: string;
  sortBy: ProviderSortField;
}

type ProviderFormMode = "create" | "edit";
type ProviderFormSection =
  "provider" | "identity" | "settings" | "credentials" | "review";

interface ProviderFormValues {
  config: Record<string, ProviderFieldValue>;
  name: string;
  provider: string;
}

interface ProviderWriteValues extends ProviderFormValues {
  secrets: Record<string, string | null>;
}

interface ProviderDraftContext {
  capability: ProviderCapability;
  configId: string | null;
  memberKey: string;
  organizationId: string;
}

interface StoredProviderDraft {
  savedAt: string;
  values: ProviderFormValues;
  version: 1;
}

const PROVIDER_CAPABILITIES = [
  "llm",
  "stt",
  "tts",
  "realtime",
  "webrtc",
  "telephony",
  "email",
  "storage",
  "embedding",
  "reranking",
  "memory",
  "sandbox",
] as const satisfies readonly ProviderCapability[];

export { PROVIDER_CAPABILITIES };
export type {
  ProviderCapabilities,
  ProviderCapability,
  ProviderCapabilityDefinition,
  ProviderCapabilityStatus,
  ProviderCatalog,
  ProviderConfigCreateInput,
  ProviderConfigRecord,
  ProviderConfigResponse,
  ProviderConfigUpdateInput,
  ProviderCollectionQuery,
  ProviderDefinition,
  ProviderDraftContext,
  ProviderFieldDefinition,
  ProviderFieldValue,
  ProviderReferenceField,
  ProviderReferenceOption,
  ProviderFilterProperty,
  ProviderFormMode,
  ProviderFormSection,
  ProviderFormValues,
  ProviderSortDirection,
  ProviderSortField,
  ProviderTool,
  ProviderWriteValues,
  StoredProviderDraft,
};
