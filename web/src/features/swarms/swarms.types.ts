import type { components } from "@/api/generated/schema";
import type { Agent } from "@/features/agents/agents.types";
import type { FilterGroup } from "@/lib/filters";

type Swarm = components["schemas"]["AgentSwarmResponseSchema"];
type SwarmMember = components["schemas"]["AgentSwarmMappingResponseSchema"];
type SwarmRevision = components["schemas"]["AgentSwarmRevisionResponseSchema"];
type SwarmCreateInput = components["schemas"]["AgentSwarmCreateRequestSchema"];
type SwarmUpdateInput = components["schemas"]["AgentSwarmUpdateRequestSchema"];
type SwarmMemberCreateInput =
  components["schemas"]["AgentSwarmMappingCreateRequestSchema"];
type SwarmMemberDeleteInput =
  components["schemas"]["AgentSwarmMappingDeleteRequestSchema"];
type SwarmLifecycle = "draft" | "published" | "withdrawn" | "archived";
type SwarmSortDirection = "asc" | "desc";
type SwarmSortField = "name" | "lifecycle" | "created_at" | "updated_at";
type SwarmFilterProperty = "lifecycle";
type SwarmFormMode = "create" | "edit";

interface SwarmCollectionQuery {
  direction: SwarmSortDirection;
  filters: FilterGroup<SwarmFilterProperty>;
  limit: number;
  page: number;
  search: string;
  sortBy: SwarmSortField;
}

interface SwarmFormValues {
  description: string;
  name: string;
}

interface SwarmMemberView {
  agent: Agent | null;
  mapping: SwarmMember;
}

const SWARM_LIFECYCLES = [
  "draft",
  "published",
  "withdrawn",
  "archived",
] as const satisfies readonly SwarmLifecycle[];
const SWARM_SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly SwarmSortDirection[];
const SWARM_SORT_FIELDS = [
  "name",
  "lifecycle",
  "created_at",
  "updated_at",
] as const satisfies readonly SwarmSortField[];
const SWARMS_PAGE_SIZE = 20;

export {
  SWARM_LIFECYCLES,
  SWARM_SORT_DIRECTIONS,
  SWARM_SORT_FIELDS,
  SWARMS_PAGE_SIZE,
};
export type {
  Swarm,
  SwarmCollectionQuery,
  SwarmCreateInput,
  SwarmFilterProperty,
  SwarmFormMode,
  SwarmFormValues,
  SwarmLifecycle,
  SwarmMember,
  SwarmMemberCreateInput,
  SwarmMemberDeleteInput,
  SwarmMemberView,
  SwarmRevision,
  SwarmSortDirection,
  SwarmSortField,
  SwarmUpdateInput,
};
