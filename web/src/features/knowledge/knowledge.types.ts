import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type Knowledgebase = components["schemas"]["KnowledgebaseRead"];
type KnowledgebaseCreateInput = components["schemas"]["KnowledgebaseCreate"];
type KnowledgebaseUpdateInput = components["schemas"]["KnowledgebaseUpdate"];
type KnowledgeScope = components["schemas"]["KnowledgeScope"];
type KnowledgeChunkingStrategy =
  components["schemas"]["KnowledgeChunkingStrategy"];
type KnowledgebaseMetadata = components["schemas"]["KnowledgebaseMetadata"];
type CorpusImport = components["schemas"]["CorpusImportRead"];
type CorpusImportInput = components["schemas"]["CorpusImportRequest"];
type EmbeddingConfig = components["schemas"]["EmbeddingConfigResponse"];
type IngestionInput = components["schemas"]["IngestRequest"];
type IngestionJob = components["schemas"]["IngestionJobRead"];
type KnowledgeDurableState = components["schemas"]["DurableState"];
type KnowledgeReindexJob = components["schemas"]["KnowledgeReindexJobRead"];
type KnowledgeReindexStatus =
  components["schemas"]["KnowledgeReindexStatusRead"];
type StorageConfig = components["schemas"]["StorageConfigResponse"];

const KNOWLEDGE_VENDORS = ["postgres_fts", "pgvector"] as const;
type KnowledgeVendor = (typeof KNOWLEDGE_VENDORS)[number];

const KNOWLEDGE_CHUNKING_STRATEGIES = [
  "paragraph",
  "markdown",
  "fixed",
] as const satisfies readonly KnowledgeChunkingStrategy[];

type KnowledgebaseFormMode = "create" | "edit";

interface KnowledgebaseFormValues {
  chunkOverlap: string;
  chunkSize: string;
  chunking: KnowledgeChunkingStrategy;
  embeddingProviderConfigId: string | null;
  name: string;
  scope: KnowledgeScope | "";
  scopeId: string;
  vendor: KnowledgeVendor | "";
  writable: boolean;
}

interface KnowledgeAgentOption {
  id: string;
  kind: string;
  label: string;
  lifecycle: string;
}

const KNOWLEDGE_SCOPES = [
  "organization",
  "agent",
  "conversation",
] as const satisfies readonly KnowledgeScope[];

type KnowledgeFilterProperty = "scope" | "vendor" | "writable";
type KnowledgeSortDirection = "asc" | "desc";
type KnowledgeSortField = "name" | "scope" | "updated_at" | "vendor";

interface KnowledgeCollectionQuery {
  direction: KnowledgeSortDirection;
  filters: FilterGroup<KnowledgeFilterProperty>;
  search: string;
  sortBy: KnowledgeSortField;
}

export { KNOWLEDGE_CHUNKING_STRATEGIES, KNOWLEDGE_SCOPES, KNOWLEDGE_VENDORS };
export type {
  CorpusImport,
  CorpusImportInput,
  EmbeddingConfig,
  IngestionInput,
  IngestionJob,
  KnowledgeAgentOption,
  KnowledgeDurableState,
  KnowledgeReindexJob,
  KnowledgeReindexStatus,
  Knowledgebase,
  KnowledgebaseCreateInput,
  KnowledgebaseFormMode,
  KnowledgebaseFormValues,
  KnowledgebaseMetadata,
  KnowledgebaseUpdateInput,
  KnowledgeChunkingStrategy,
  KnowledgeCollectionQuery,
  KnowledgeFilterProperty,
  KnowledgeScope,
  KnowledgeSortDirection,
  KnowledgeSortField,
  KnowledgeVendor,
  StorageConfig,
};
