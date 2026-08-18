import {
  AGENT_KINDS,
  AGENT_SORT_DIRECTIONS,
  AGENT_SORT_FIELDS,
  AGENT_STATUSES,
  AGENTS_PAGE_SIZE,
  type AgentCollectionQuery,
  type AgentFilterProperty,
  type AgentKind,
  type AgentListApiQuery,
  type AgentSortDirection,
  type AgentSortField,
  type AgentStatus,
} from "@/features/agents/agents.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const AGENT_FILTER_ROOT_ID = "agent-main-filters";

const DEFAULT_AGENT_QUERY: AgentCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<AgentFilterProperty>(AGENT_FILTER_ROOT_ID),
  limit: AGENTS_PAGE_SIZE,
  page: 1,
  search: "",
  sortBy: "updated_at",
};

function parseAgentCollectionQuery(
  searchParams: URLSearchParams,
): AgentCollectionQuery {
  const statuses = parseKnownValues(
    searchParams.getAll("status"),
    AGENT_STATUSES,
  );
  const kinds = parseKnownValues(searchParams.getAll("kind"), AGENT_KINDS);
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), AGENT_SORT_DIRECTIONS) ??
      DEFAULT_AGENT_QUERY.direction,
    filters: createAgentFilterTree(statuses, kinds),
    limit: AGENTS_PAGE_SIZE,
    page: parsePage(searchParams.get("page")),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), AGENT_SORT_FIELDS) ??
      DEFAULT_AGENT_QUERY.sortBy,
  };
}

function buildAgentCollectionSearchParams(
  query: AgentCollectionQuery,
): URLSearchParams {
  const searchParams = new URLSearchParams();

  if (query.search !== "") {
    searchParams.set("q", query.search);
  }
  appendKnownValues(
    searchParams,
    "status",
    getAgentFilterValues(query.filters, "status"),
    AGENT_STATUSES,
  );
  appendKnownValues(
    searchParams,
    "kind",
    getAgentFilterValues(query.filters, "kind"),
    AGENT_KINDS,
  );
  if (query.sortBy !== DEFAULT_AGENT_QUERY.sortBy) {
    searchParams.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_AGENT_QUERY.direction) {
    searchParams.set("direction", query.direction);
  }
  if (query.page > 1) {
    searchParams.set("page", String(query.page));
  }

  return searchParams;
}

function toAgentListApiQuery(query: AgentCollectionQuery): AgentListApiQuery {
  const statuses = parseKnownValues(
    getAgentFilterValues(query.filters, "status"),
    AGENT_STATUSES,
  );
  const kinds = parseKnownValues(
    getAgentFilterValues(query.filters, "kind"),
    AGENT_KINDS,
  );
  return {
    search: query.search === "" ? undefined : query.search,
    status: statuses.length === 0 ? undefined : statuses,
    kind: kinds.length === 0 ? undefined : kinds,
    sort_by: query.sortBy,
    sort_direction: query.direction,
    page: query.page,
    limit: query.limit,
  };
}

function hasAgentCollectionFilters(query: AgentCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function getAgentFilterValues(
  filterTree: FilterGroup<AgentFilterProperty>,
  property: AgentFilterProperty,
): readonly string[] {
  const condition = filterTree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function createAgentFilterTree(
  statuses: readonly AgentStatus[],
  kinds: readonly AgentKind[],
): FilterGroup<AgentFilterProperty> {
  const children: FilterCondition<AgentFilterProperty>[] = [];
  if (statuses.length > 0) {
    children.push(createAgentFilterCondition("status", statuses));
  }
  if (kinds.length > 0) {
    children.push(createAgentFilterCondition("kind", kinds));
  }
  return {
    children,
    id: AGENT_FILTER_ROOT_ID,
    op: "and",
    type: "group",
  };
}

function createAgentFilterCondition(
  property: AgentFilterProperty,
  values: readonly string[],
): FilterCondition<AgentFilterProperty> {
  return {
    id: `agent-main-filter-${property}`,
    operator: normalizeFilterOperator("is", "multi-select", values.length),
    property,
    type: "condition",
    values,
  };
}

function appendKnownValues<T extends string>(
  searchParams: URLSearchParams,
  key: string,
  values: readonly string[],
  knownValues: readonly T[],
): void {
  for (const value of knownValues) {
    if (values.includes(value)) {
      searchParams.append(key, value);
    }
  }
}

function parsePage(value: string | null): number {
  if (value === null || !/^\d+$/.test(value)) {
    return 1;
  }

  const page = Number(value);
  return Number.isSafeInteger(page) && page > 0 ? page : 1;
}

function parseKnownValue<T extends string>(
  value: string | null,
  knownValues: readonly T[],
): T | null {
  return value !== null && knownValues.includes(value as T)
    ? (value as T)
    : null;
}

function parseKnownValues<T extends string>(
  values: readonly string[],
  knownValues: readonly T[],
): T[] {
  return knownValues.filter((knownValue) => values.includes(knownValue));
}

export {
  buildAgentCollectionSearchParams,
  DEFAULT_AGENT_QUERY,
  getAgentFilterValues,
  hasAgentCollectionFilters,
  parseAgentCollectionQuery,
  toAgentListApiQuery,
};
export type { AgentKind, AgentSortDirection, AgentSortField, AgentStatus };
