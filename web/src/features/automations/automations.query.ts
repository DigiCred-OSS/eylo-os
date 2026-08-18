import type { FilterUiSchema } from "@/components/filters";
import type {
  ScheduleCollectionQuery,
  ScheduleFilterProperty,
  ScheduleRecord,
  ScheduleSortDirection,
  ScheduleSortField,
} from "@/features/automations/automations.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "automations-main-filters";
const SORT_FIELDS = [
  "name",
  "next_at",
  "last_fired_at",
  "lifecycle",
] as const satisfies readonly ScheduleSortField[];
const DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly ScheduleSortDirection[];
const ENABLED = ["true", "false"] as const;
const LIFECYCLES = ["published", "withdrawn"] as const;
const MISFIRE_POLICIES = ["coalesce", "fire_all"] as const;

const DEFAULT_AUTOMATIONS_QUERY: ScheduleCollectionQuery = {
  direction: "asc",
  filters: createEmptyFilterGroup<ScheduleFilterProperty>(FILTER_ROOT_ID),
  search: "",
  sortBy: "next_at",
};

function parseAutomationsQuery(
  params: URLSearchParams,
): ScheduleCollectionQuery {
  return {
    direction:
      parseKnownValue(params.get("direction"), DIRECTIONS) ??
      DEFAULT_AUTOMATIONS_QUERY.direction,
    filters: createFilterTree({
      enabled: parseKnownValues(params.getAll("enabled"), ENABLED),
      lifecycles: params
        .getAll("lifecycle")
        .filter((value) => value.trim() !== ""),
      policies: parseKnownValues(params.getAll("misfire"), MISFIRE_POLICIES),
    }),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(params.get("sort"), SORT_FIELDS) ??
      DEFAULT_AUTOMATIONS_QUERY.sortBy,
  };
}

function buildAutomationsSearchParams(
  query: ScheduleCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  appendValues(
    params,
    "enabled",
    filterValues(query.filters, "enabled"),
    ENABLED,
  );
  appendValues(
    params,
    "lifecycle",
    filterValues(query.filters, "lifecycle"),
    LIFECYCLES,
  );
  appendValues(
    params,
    "misfire",
    filterValues(query.filters, "misfire_policy"),
    MISFIRE_POLICIES,
  );
  if (query.sortBy !== DEFAULT_AUTOMATIONS_QUERY.sortBy)
    params.set("sort", query.sortBy);
  if (query.direction !== DEFAULT_AUTOMATIONS_QUERY.direction)
    params.set("direction", query.direction);
  return params;
}

function applyAutomationsQuery(
  items: readonly ScheduleRecord[],
  query: ScheduleCollectionQuery,
  schema: FilterUiSchema<ScheduleRecord, ScheduleFilterProperty>,
): ScheduleRecord[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [item.name, item.key, item.action, item.timezone]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort((left, right) => {
    const compared = compareSchedules(left, right, query.sortBy);
    const directed = query.direction === "asc" ? compared : -compared;
    return directed !== 0 ? directed : left.id.localeCompare(right.id);
  });
}

function createFilterTree(values: {
  enabled: readonly string[];
  lifecycles: readonly string[];
  policies: readonly string[];
}): FilterGroup<ScheduleFilterProperty> {
  const children: FilterCondition<ScheduleFilterProperty>[] = [];
  for (const [property, selected, valueType] of [
    ["enabled", values.enabled, "single-select"],
    ["lifecycle", values.lifecycles, "multi-select"],
    ["misfire_policy", values.policies, "multi-select"],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `automations-main-filter-${property}`,
        operator: normalizeFilterOperator("is", valueType, selected.length),
        property,
        type: "condition",
        values: [...selected],
      });
    }
  }
  return { children, id: FILTER_ROOT_ID, op: "and", type: "group" };
}

function filterValues(
  tree: FilterGroup<ScheduleFilterProperty>,
  property: ScheduleFilterProperty,
): readonly string[] {
  const node = tree.children.find(
    (child) => child.type === "condition" && child.property === property,
  );
  return node?.type === "condition" ? node.values : [];
}

function compareSchedules(
  left: ScheduleRecord,
  right: ScheduleRecord,
  field: ScheduleSortField,
): number {
  if (field === "name")
    return left.name.localeCompare(right.name, undefined, {
      sensitivity: "base",
    });
  if (field === "lifecycle")
    return left.lifecycle.localeCompare(right.lifecycle);
  return toTimestamp(left[field]) - toTimestamp(right[field]);
}

function toTimestamp(value: string | null): number {
  if (value === null) return Number.MAX_SAFE_INTEGER;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? Number.MAX_SAFE_INTEGER : timestamp;
}

function appendValues(
  params: URLSearchParams,
  key: string,
  values: readonly string[],
  known: readonly string[],
): void {
  for (const value of known)
    if (values.includes(value)) params.append(key, value);
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

function hasAutomationFilters(query: ScheduleCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

export {
  applyAutomationsQuery,
  buildAutomationsSearchParams,
  DEFAULT_AUTOMATIONS_QUERY,
  hasAutomationFilters,
  parseAutomationsQuery,
};
