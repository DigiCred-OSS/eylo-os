import type { components, operations } from "@/api/generated/schema";
import type {
  ProviderReferenceField,
  ProviderReferenceOption,
} from "@/features/providers/providers.types";
import type { FilterGroup } from "@/lib/filters";

type Agent = components["schemas"]["AgentResponseSchema"];
type AgentEffectiveVoiceStack =
  components["schemas"]["AgentEffectiveVoiceStackResponseSchema"];
type AgentRevisionReference =
  components["schemas"]["AgentRevisionReferenceSchema"];
type AgentBackgroundAttachment =
  components["schemas"]["AgentBackgroundAgentInDb"];
type AgentCreateInput = components["schemas"]["AgentCreateRequestSchema"];
type AgentKind = components["schemas"]["AgentKind"];
type AgentLlmOverrides = components["schemas"]["LLMOverridesSchema"];
type AgentLlmModel = NonNullable<AgentLlmOverrides["model"]>;
type AgentKnowledgeAccess = components["schemas"]["KnowledgeAccess"];
type AgentKnowledgebase = components["schemas"]["KnowledgebaseRead"];
type AgentKnowledgebaseGrant = components["schemas"]["GrantRead"];
type AgentSandboxConfig = components["schemas"]["SandboxConfigResponse"];
type AgentSandboxGrant = components["schemas"]["SandboxGrantRead"];
type AgentsPaginated = components["schemas"]["AgentsPaginated"];
type AgentSortDirection = components["schemas"]["AgentSortDirection"];
type AgentSortField = components["schemas"]["AgentSortField"];
type AgentStatus = components["schemas"]["AgentStatus"];
type AgentUpdateInput = components["schemas"]["AgentUpdateRequestSchema"];
type AgentInstructionTemplate = components["schemas"]["TemplateResponse"];
type AgentInstructionTemplateCreateInput =
  components["schemas"]["TemplateCreateRequest"];
type AgentInstructionTemplateUpdateInput =
  components["schemas"]["TemplateDraftUpdateRequest"];
type Tool = components["schemas"]["ToolResponseSchema"];
type CuratedTool = components["schemas"]["InstalledToolSchema"];
interface AgentCuratedTool extends CuratedTool {
  vendor: string;
  vendorDisplayName: string;
}
type AgentListApiQuery = NonNullable<
  operations["list_agents_api__organization_id__agents_get"]["parameters"]["query"]
>;

interface AgentCollectionQuery {
  direction: AgentSortDirection;
  filters: FilterGroup<AgentFilterProperty>;
  limit: number;
  page: number;
  search: string;
  sortBy: AgentSortField;
}

type AgentFilterProperty = "status" | "kind";

type AgentFormMode = "create" | "edit";
type AgentFormSection =
  "basics" | "runtime" | "providers" | "voice" | "relationships" | "lifecycle";
type AgentReferenceField = ProviderReferenceField;

interface AgentFormValues {
  allowFileUploads: boolean;
  description: string;
  emailProviderConfigId: string | null;
  fileUploadEmbeddingProviderConfigId: string | null;
  instructionTemplateId: string | null;
  kind: AgentKind;
  llmOverrides: AgentLlmOverrideValues;
  llmProviderConfigId: string | null;
  memoryProviderConfigId: string | null;
  name: string;
  rerankingProviderConfigId: string | null;
  voiceConfigId: string | null;
  webrtcProviderConfigId: string | null;
}

interface AgentLlmOverrideValues {
  maxTokens: number | null;
  model: AgentLlmModel | null;
  stopSequences: string[];
  temperature: number | null;
  topK: number | null;
  topP: number | null;
}

type AgentReferenceOption = ProviderReferenceOption;

const AGENT_KINDS = [
  "CONVERSATIONAL",
  "BACKGROUND",
] as const satisfies readonly AgentKind[];
const AGENT_STATUSES = [
  "DRAFT",
  "ACTIVE",
  "INACTIVE",
  "ARCHIVED",
] as const satisfies readonly AgentStatus[];
const AGENT_SORT_FIELDS = [
  "name",
  "status",
  "kind",
  "created_at",
  "updated_at",
] as const satisfies readonly AgentSortField[];
const AGENT_SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly AgentSortDirection[];
const AGENTS_PAGE_SIZE = 20;

export {
  AGENT_KINDS,
  AGENT_SORT_DIRECTIONS,
  AGENT_SORT_FIELDS,
  AGENT_STATUSES,
  AGENTS_PAGE_SIZE,
};
export type {
  Agent,
  AgentBackgroundAttachment,
  AgentCollectionQuery,
  AgentCreateInput,
  AgentCuratedTool,
  AgentEffectiveVoiceStack,
  AgentFormMode,
  AgentFormSection,
  AgentFormValues,
  AgentFilterProperty,
  AgentKind,
  AgentKnowledgeAccess,
  AgentKnowledgebase,
  AgentKnowledgebaseGrant,
  AgentInstructionTemplate,
  AgentInstructionTemplateCreateInput,
  AgentInstructionTemplateUpdateInput,
  AgentListApiQuery,
  AgentLlmModel,
  AgentLlmOverrides,
  AgentLlmOverrideValues,
  AgentReferenceField,
  AgentReferenceOption,
  AgentRevisionReference,
  AgentSandboxConfig,
  AgentSandboxGrant,
  AgentsPaginated,
  AgentSortDirection,
  AgentSortField,
  AgentStatus,
  AgentUpdateInput,
  Tool,
};
