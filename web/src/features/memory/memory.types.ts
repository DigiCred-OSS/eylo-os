import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type Memory = components["schemas"]["MemoryRead"];
type MemoryDetail = components["schemas"]["MemoryDetailRead"];
type MemoryLevel = components["schemas"]["MemoryLevel"];
type MemoryStatus = components["schemas"]["MemoryStatus"];
type MemoryIntegrity = components["schemas"]["MemoryIntegrityState"];
type MemoryRelationship = components["schemas"]["MemoryRelationshipRead"];
type MemoryReconciliationJob =
  components["schemas"]["MemoryReconciliationJobRead"];
type MemoryReindexJob = components["schemas"]["MemoryReindexJobRead"];
type MemoryReindexStatus = components["schemas"]["MemoryReindexStatusRead"];

const MEMORY_LEVELS = [
  "agent",
  "user",
  "conversation",
] as const satisfies readonly MemoryLevel[];
const MEMORY_STATUSES = [
  "active",
  "expired",
] as const satisfies readonly MemoryStatus[];
const MEMORY_RECALL_STATES = ["recalled", "not_recalled"] as const;
const MEMORY_INTEGRITIES = [
  "checking",
  "conflicted",
  "consolidated",
  "healthy",
] as const satisfies readonly MemoryIntegrity[];

type MemoryRecallState = (typeof MEMORY_RECALL_STATES)[number];
type MemoryFilterProperty = "integrity" | "level" | "recalled" | "status";
type MemorySortDirection = "asc" | "desc";
type MemorySortField =
  | "created_at"
  | "expires_at"
  | "last_recalled_at"
  | "recall_count"
  | "updated_at";

interface MemoryCollectionQuery {
  direction: MemorySortDirection;
  filters: FilterGroup<MemoryFilterProperty>;
  search: string;
  sortBy: MemorySortField;
}

interface MemoryListRequest {
  direction: MemorySortDirection;
  integrities: MemoryIntegrity[];
  levels: MemoryLevel[];
  offset: number;
  query: string;
  recalled: boolean | null;
  sort: MemorySortField;
  statuses: MemoryStatus[];
}

export {
  MEMORY_INTEGRITIES,
  MEMORY_LEVELS,
  MEMORY_RECALL_STATES,
  MEMORY_STATUSES,
};
export type {
  Memory,
  MemoryCollectionQuery,
  MemoryDetail,
  MemoryFilterProperty,
  MemoryIntegrity,
  MemoryLevel,
  MemoryListRequest,
  MemoryRecallState,
  MemoryReconciliationJob,
  MemoryReindexJob,
  MemoryReindexStatus,
  MemoryRelationship,
  MemorySortDirection,
  MemorySortField,
  MemoryStatus,
};
