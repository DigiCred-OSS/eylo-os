import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type AgentRun = components["schemas"]["AgentRunRead"];
type OperationAgent = components["schemas"]["AgentResponseSchema"];
type AgentInputRequest = components["schemas"]["AgentInputRequestRead"];
type ExecutionBudget = components["schemas"]["OrganizationExecutionBudgetRead"];
type ExecutionBudgetInput =
  components["schemas"]["OrganizationExecutionBudgetUpsert"];
type EventHealth = components["schemas"]["EventHealthResponse"];
type VoiceSession = components["schemas"]["VoiceSessionSummary"];
type VoiceSessionDetail = components["schemas"]["VoiceSessionDetail"];

type AgentRunFilterProperty = "lifecycle" | "origin" | "outcome";
type AgentRunSortField = "created_at" | "goal" | "lifecycle" | "updated_at";
type VoiceSessionFilterProperty = "runtime" | "status" | "canonical_state";
type VoiceSessionSortField = "started_at" | "duration" | "status" | "segments";
type OperationSortDirection = "asc" | "desc";

interface AgentRunCollectionQuery {
  direction: OperationSortDirection;
  filters: FilterGroup<AgentRunFilterProperty>;
  search: string;
  sortBy: AgentRunSortField;
}

interface VoiceSessionCollectionQuery {
  direction: OperationSortDirection;
  filters: FilterGroup<VoiceSessionFilterProperty>;
  search: string;
  sortBy: VoiceSessionSortField;
}

interface ServiceHealth {
  checkedAt: string;
  latencyMs: number;
  online: boolean;
}

export type {
  AgentInputRequest,
  AgentRun,
  AgentRunCollectionQuery,
  AgentRunFilterProperty,
  AgentRunSortField,
  EventHealth,
  ExecutionBudget,
  ExecutionBudgetInput,
  OperationSortDirection,
  OperationAgent,
  ServiceHealth,
  VoiceSession,
  VoiceSessionCollectionQuery,
  VoiceSessionDetail,
  VoiceSessionFilterProperty,
  VoiceSessionSortField,
};
