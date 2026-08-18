import type { FilterUiSchema } from "@/components/filters";
import type {
  ProviderCollectionQuery,
  ProviderConfigRecord,
  ProviderFilterProperty,
  ProviderSortDirection,
  ProviderSortField,
} from "@/features/providers/providers.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "provider-main-filters";
const SORT_FIELDS = [
  "name",
  "provider",
  "ready",
  "verified_at",
] as const satisfies readonly ProviderSortField[];
const SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly ProviderSortDirection[];
const BOOLEAN_VALUES = ["true", "false"] as const;

const DEFAULT_PROVIDER_QUERY: ProviderCollectionQuery = {
  direction: "asc",
  filters: createEmptyFilterGroup<ProviderFilterProperty>(FILTER_ROOT_ID),
  search: "",
  sortBy: "name",
};

function parseProviderCollectionQuery(
  searchParams: URLSearchParams,
  providerIds: readonly string[],
): ProviderCollectionQuery {
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), SORT_DIRECTIONS) ??
      DEFAULT_PROVIDER_QUERY.direction,
    filters: createFilterTree({
      enabled: parseKnownValues(searchParams.getAll("enabled"), BOOLEAN_VALUES),
      provider: providerIds.filter((value) =>
        searchParams.getAll("provider").includes(value),
      ),
      ready: parseKnownValues(searchParams.getAll("ready"), BOOLEAN_VALUES),
      verified: parseKnownValues(
        searchParams.getAll("verified"),
        BOOLEAN_VALUES,
      ),
    }),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), SORT_FIELDS) ??
      DEFAULT_PROVIDER_QUERY.sortBy,
  };
}

function buildProviderCollectionSearchParams(
  query: ProviderCollectionQuery,
  providerIds: readonly string[],
): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (query.search !== "") {
    searchParams.set("q", query.search);
  }
  appendKnownValues(
    searchParams,
    "provider",
    filterValues(query.filters, "provider"),
    providerIds,
  );
  for (const property of ["ready", "verified", "enabled"] as const) {
    appendKnownValues(
      searchParams,
      property,
      filterValues(query.filters, property),
      BOOLEAN_VALUES,
    );
  }
  if (query.sortBy !== DEFAULT_PROVIDER_QUERY.sortBy) {
    searchParams.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_PROVIDER_QUERY.direction) {
    searchParams.set("direction", query.direction);
  }
  return searchParams;
}

function applyProviderCollectionQuery(
  items: readonly ProviderConfigRecord[],
  query: ProviderCollectionQuery,
  schema: FilterUiSchema<ProviderConfigRecord, ProviderFilterProperty>,
): ProviderConfigRecord[] {
  const search = query.search.toLocaleLowerCase();
  const searched =
    search === ""
      ? [...items]
      : items.filter(
          (item) =>
            item.name.toLocaleLowerCase().includes(search) ||
            item.provider.toLocaleLowerCase().includes(search),
        );
  const filtered = applyFilters(searched, query.filters, schema);
  return filtered.sort((left, right) => {
    const compared = compareProviderConfigs(left, right, query.sortBy);
    const directed = query.direction === "asc" ? compared : -compared;
    return directed !== 0 ? directed : left.id.localeCompare(right.id);
  });
}

function createFilterTree(values: {
  enabled: readonly string[];
  provider: readonly string[];
  ready: readonly string[];
  verified: readonly string[];
}): FilterGroup<ProviderFilterProperty> {
  const children: FilterCondition<ProviderFilterProperty>[] = [];
  for (const property of [
    "provider",
    "ready",
    "verified",
    "enabled",
  ] as const) {
    if (values[property].length > 0) {
      children.push({
        id: `provider-main-filter-${property}`,
        operator: normalizeFilterOperator(
          "is",
          property === "provider" ? "multi-select" : "single-select",
          values[property].length,
        ),
        property,
        type: "condition",
        values: values[property],
      });
    }
  }
  return { children, id: FILTER_ROOT_ID, op: "and", type: "group" };
}

function filterValues(
  tree: FilterGroup<ProviderFilterProperty>,
  property: ProviderFilterProperty,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function compareProviderConfigs(
  left: ProviderConfigRecord,
  right: ProviderConfigRecord,
  field: ProviderSortField,
): number {
  if (field === "ready") {
    return Number(left.ready) - Number(right.ready);
  }
  if (field === "verified_at") {
    return toTimestamp(left.verifiedAt) - toTimestamp(right.verifiedAt);
  }
  return left[field].localeCompare(right[field], undefined, {
    sensitivity: "base",
  });
}

function toTimestamp(value: string | null): number {
  if (value === null) {
    return 0;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function appendKnownValues(
  searchParams: URLSearchParams,
  key: string,
  values: readonly string[],
  knownValues: readonly string[],
): void {
  for (const value of knownValues) {
    if (values.includes(value)) {
      searchParams.append(key, value);
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

function hasProviderCollectionFilters(query: ProviderCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

export {
  applyProviderCollectionQuery,
  buildProviderCollectionSearchParams,
  DEFAULT_PROVIDER_QUERY,
  hasProviderCollectionFilters,
  parseProviderCollectionQuery,
};
