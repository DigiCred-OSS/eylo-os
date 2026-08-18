import {
  SWARM_LIFECYCLES,
  SWARM_SORT_DIRECTIONS,
  SWARM_SORT_FIELDS,
  SWARMS_PAGE_SIZE,
  type Swarm,
  type SwarmCollectionQuery,
  type SwarmFilterProperty,
  type SwarmLifecycle,
} from "@/features/swarms/swarms.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "swarm-main-filters";

const DEFAULT_SWARM_QUERY: SwarmCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<SwarmFilterProperty>(FILTER_ROOT_ID),
  limit: SWARMS_PAGE_SIZE,
  page: 1,
  search: "",
  sortBy: "updated_at",
};

function parseSwarmCollectionQuery(
  searchParams: URLSearchParams,
): SwarmCollectionQuery {
  const lifecycles = parseKnownValues(
    searchParams.getAll("lifecycle"),
    SWARM_LIFECYCLES,
  );
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), SWARM_SORT_DIRECTIONS) ??
      DEFAULT_SWARM_QUERY.direction,
    filters: createFilterTree(lifecycles),
    limit: SWARMS_PAGE_SIZE,
    page: parsePage(searchParams.get("page")),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), SWARM_SORT_FIELDS) ??
      DEFAULT_SWARM_QUERY.sortBy,
  };
}

function buildSwarmCollectionSearchParams(
  query: SwarmCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  for (const lifecycle of SWARM_LIFECYCLES) {
    if (getSwarmFilterValues(query.filters).includes(lifecycle)) {
      params.append("lifecycle", lifecycle);
    }
  }
  if (query.sortBy !== DEFAULT_SWARM_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_SWARM_QUERY.direction) {
    params.set("direction", query.direction);
  }
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}

function applySwarmCollectionQuery(
  swarms: readonly Swarm[],
  query: SwarmCollectionQuery,
): { items: Swarm[]; total: number } {
  const search = query.search.toLocaleLowerCase();
  const lifecycles = getSwarmFilterValues(query.filters);
  const filtered = swarms.filter((swarm) => {
    if (
      search !== "" &&
      ![swarm.name, swarm.slug, swarm.description ?? ""].some((value) =>
        value.toLocaleLowerCase().includes(search),
      )
    ) {
      return false;
    }
    return lifecycles.length === 0 || lifecycles.includes(swarm.lifecycle);
  });
  const direction = query.direction === "asc" ? 1 : -1;
  filtered.sort((left, right) => {
    const comparison = swarmSortValue(left, query.sortBy).localeCompare(
      swarmSortValue(right, query.sortBy),
      undefined,
      { sensitivity: "base" },
    );
    return comparison === 0
      ? left.id.localeCompare(right.id) * direction
      : comparison * direction;
  });
  const start = (query.page - 1) * query.limit;
  return {
    items: filtered.slice(start, start + query.limit),
    total: filtered.length,
  };
}

function hasSwarmCollectionFilters(query: SwarmCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function getSwarmFilterValues(
  tree: FilterGroup<SwarmFilterProperty>,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === "lifecycle",
  );
  return condition?.type === "condition" ? condition.values : [];
}

function createFilterTree(
  lifecycles: readonly SwarmLifecycle[],
): FilterGroup<SwarmFilterProperty> {
  const children: FilterCondition<SwarmFilterProperty>[] = [];
  if (lifecycles.length > 0) {
    children.push({
      id: "swarm-main-filter-lifecycle",
      operator: normalizeFilterOperator(
        "is",
        "multi-select",
        lifecycles.length,
      ),
      property: "lifecycle",
      type: "condition",
      values: [...lifecycles],
    });
  }
  return { children, id: FILTER_ROOT_ID, op: "and", type: "group" };
}

function swarmSortValue(
  swarm: Swarm,
  field: SwarmCollectionQuery["sortBy"],
): string {
  switch (field) {
    case "name":
      return swarm.name;
    case "lifecycle":
      return swarm.lifecycle;
    case "created_at":
      return swarm.createdAt ?? "";
    case "updated_at":
      return swarm.updatedAt ?? "";
  }
}

function parsePage(value: string | null): number {
  if (value === null || !/^\d+$/.test(value)) return 1;
  const page = Number(value);
  return Number.isSafeInteger(page) && page > 0 ? page : 1;
}

function parseKnownValue<Value extends string>(
  value: string | null,
  known: readonly Value[],
): Value | null {
  return value !== null && known.includes(value as Value)
    ? (value as Value)
    : null;
}

function parseKnownValues<Value extends string>(
  values: readonly string[],
  known: readonly Value[],
): Value[] {
  return known.filter((value) => values.includes(value));
}

export {
  applySwarmCollectionQuery,
  buildSwarmCollectionSearchParams,
  DEFAULT_SWARM_QUERY,
  getSwarmFilterValues,
  hasSwarmCollectionFilters,
  parseSwarmCollectionQuery,
};
