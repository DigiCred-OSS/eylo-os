import type {
  MemoryCollectionQuery,
  MemoryFilterProperty,
  MemoryIntegrity,
  MemoryLevel,
  MemoryListRequest,
  MemoryRecallState,
  MemorySortDirection,
  MemorySortField,
  MemoryStatus,
} from "@/features/memory/memory.types";
import {
  MEMORY_LEVELS,
  MEMORY_INTEGRITIES,
  MEMORY_RECALL_STATES,
  MEMORY_STATUSES,
} from "@/features/memory/memory.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "memory-main-filters";
const SORT_FIELDS = [
  "updated_at",
  "created_at",
  "last_recalled_at",
  "expires_at",
  "recall_count",
] as const satisfies readonly MemorySortField[];
const SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly MemorySortDirection[];

const DEFAULT_MEMORY_QUERY: MemoryCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<MemoryFilterProperty>(FILTER_ROOT_ID),
  search: "",
  sortBy: "updated_at",
};

function parseMemoryCollectionQuery(
  searchParams: URLSearchParams,
): MemoryCollectionQuery {
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), SORT_DIRECTIONS) ??
      DEFAULT_MEMORY_QUERY.direction,
    filters: createFilterTree({
      integrities: parseKnownValues(
        searchParams.getAll("integrity"),
        MEMORY_INTEGRITIES,
      ),
      levels: parseKnownValues(searchParams.getAll("level"), MEMORY_LEVELS),
      recalled: parseKnownValues(
        searchParams.getAll("recalled"),
        MEMORY_RECALL_STATES,
      ),
      statuses: parseKnownValues(
        searchParams.getAll("status"),
        MEMORY_STATUSES,
      ),
    }),
    search: searchParams.get("q")?.trim().slice(0, 200) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), SORT_FIELDS) ??
      DEFAULT_MEMORY_QUERY.sortBy,
  };
}

function buildMemoryCollectionSearchParams(
  query: MemoryCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") {
    params.set("q", query.search);
  }
  appendKnownValues(
    params,
    "integrity",
    filterValues(query.filters, "integrity"),
    MEMORY_INTEGRITIES,
  );
  appendKnownValues(
    params,
    "level",
    filterValues(query.filters, "level"),
    MEMORY_LEVELS,
  );
  appendKnownValues(
    params,
    "status",
    filterValues(query.filters, "status"),
    MEMORY_STATUSES,
  );
  appendKnownValues(
    params,
    "recalled",
    filterValues(query.filters, "recalled"),
    MEMORY_RECALL_STATES,
  );
  if (query.sortBy !== DEFAULT_MEMORY_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_MEMORY_QUERY.direction) {
    params.set("direction", query.direction);
  }
  return params;
}

function toMemoryListRequest(
  query: MemoryCollectionQuery,
  offset: number,
): MemoryListRequest {
  const recalled = filterValues(query.filters, "recalled")[0];
  return {
    direction: query.direction,
    integrities: filterValues(query.filters, "integrity") as MemoryIntegrity[],
    levels: filterValues(query.filters, "level") as MemoryLevel[],
    offset,
    query: query.search,
    recalled:
      recalled === "recalled"
        ? true
        : recalled === "not_recalled"
          ? false
          : null,
    sort: query.sortBy,
    statuses: filterValues(query.filters, "status") as MemoryStatus[],
  };
}

function hasMemoryCollectionFilters(query: MemoryCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function createFilterTree(values: {
  integrities: readonly MemoryIntegrity[];
  levels: readonly MemoryLevel[];
  recalled: readonly MemoryRecallState[];
  statuses: readonly MemoryStatus[];
}): FilterGroup<MemoryFilterProperty> {
  const children: FilterCondition<MemoryFilterProperty>[] = [];
  for (const [property, selected] of [
    ["integrity", values.integrities],
    ["level", values.levels],
    ["status", values.statuses],
    ["recalled", values.recalled],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `memory-main-filter-${property}`,
        operator: normalizeFilterOperator(
          "is",
          property === "recalled" ? "single-select" : "multi-select",
          selected.length,
        ),
        property,
        type: "condition",
        values: [...selected],
      });
    }
  }
  return { children, id: FILTER_ROOT_ID, op: "and", type: "group" };
}

function filterValues(
  tree: FilterGroup<MemoryFilterProperty>,
  property: MemoryFilterProperty,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function appendKnownValues(
  params: URLSearchParams,
  key: string,
  values: readonly string[],
  knownValues: readonly string[],
): void {
  for (const value of knownValues) {
    if (values.includes(value)) {
      params.append(key, value);
    }
  }
}

function parseKnownValue<Value extends string>(
  value: string | null,
  knownValues: readonly Value[],
): Value | null {
  return value !== null && knownValues.includes(value as Value)
    ? (value as Value)
    : null;
}

function parseKnownValues<Value extends string>(
  values: readonly string[],
  knownValues: readonly Value[],
): Value[] {
  return knownValues.filter((knownValue) => values.includes(knownValue));
}

export {
  buildMemoryCollectionSearchParams,
  DEFAULT_MEMORY_QUERY,
  hasMemoryCollectionFilters,
  parseMemoryCollectionQuery,
  toMemoryListRequest,
};
