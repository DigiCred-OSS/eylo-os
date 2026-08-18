import type { FilterUiSchema } from "@/components/filters";
import type {
  ToolCapability,
  ToolCollectionQuery,
  ToolFilterProperty,
  ToolRecord,
  ToolSortDirection,
  ToolSortField,
  ToolSource,
} from "@/features/tools/tools.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "tools-main-filters";
const SOURCES = [
  "managed",
  "system",
  "provider",
] as const satisfies readonly ToolSource[];
const SORT_FIELDS = [
  "display_name",
  "kind",
  "lifecycle",
  "updated_at",
] as const satisfies readonly ToolSortField[];
const DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly ToolSortDirection[];
const CAPABILITIES = [
  "llm",
  "stt",
  "tts",
  "realtime",
  "webrtc",
  "telephony",
  "email",
  "storage",
  "embedding",
  "reranking",
  "memory",
  "sandbox",
] as const satisfies readonly ToolCapability[];
const KINDS = ["LOCAL", "SYSTEM", "MCP", "CURATED"] as const;
const LIFECYCLES = ["draft", "published", "withdrawn", "archived"] as const;
const EXECUTION_MODES = ["auto", "requires_approval", "disabled"] as const;

const DEFAULT_TOOLS_QUERY: ToolCollectionQuery = {
  capability: "llm",
  direction: "asc",
  filters: createEmptyFilterGroup<ToolFilterProperty>(FILTER_ROOT_ID),
  search: "",
  sortBy: "display_name",
  source: "system",
};

function parseToolsQuery(searchParams: URLSearchParams): ToolCollectionQuery {
  return {
    capability:
      parseKnownValue(searchParams.get("capability"), CAPABILITIES) ??
      DEFAULT_TOOLS_QUERY.capability,
    direction:
      parseKnownValue(searchParams.get("direction"), DIRECTIONS) ??
      DEFAULT_TOOLS_QUERY.direction,
    filters: createFilterTree({
      executionModes: parseKnownValues(
        searchParams.getAll("execution_mode"),
        EXECUTION_MODES,
      ),
      kinds: parseKnownValues(searchParams.getAll("kind"), KINDS),
      lifecycles: parseKnownValues(
        searchParams.getAll("lifecycle"),
        LIFECYCLES,
      ),
    }),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), SORT_FIELDS) ??
      DEFAULT_TOOLS_QUERY.sortBy,
    source:
      parseKnownValue(searchParams.get("source"), SOURCES) ??
      DEFAULT_TOOLS_QUERY.source,
  };
}

function buildToolsSearchParams(query: ToolCollectionQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.source !== DEFAULT_TOOLS_QUERY.source) {
    params.set("source", query.source);
  }
  if (query.source === "provider") {
    params.set("capability", query.capability);
  }
  if (query.search !== "") {
    params.set("q", query.search);
  }
  appendValues(params, "kind", filterValues(query.filters, "kind"), KINDS);
  appendValues(
    params,
    "lifecycle",
    filterValues(query.filters, "lifecycle"),
    LIFECYCLES,
  );
  appendValues(
    params,
    "execution_mode",
    filterValues(query.filters, "execution_mode"),
    EXECUTION_MODES,
  );
  if (query.sortBy !== DEFAULT_TOOLS_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_TOOLS_QUERY.direction) {
    params.set("direction", query.direction);
  }
  return params;
}

function applyToolsQuery(
  items: readonly ToolRecord[],
  query: ToolCollectionQuery,
  schema: FilterUiSchema<ToolRecord, ToolFilterProperty>,
): ToolRecord[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [item.displayName, item.name, item.description, item.slug]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort((left, right) => {
    const compared = compareTools(left, right, query.sortBy);
    const directed = query.direction === "asc" ? compared : -compared;
    return directed !== 0 ? directed : left.id.localeCompare(right.id);
  });
}

function createFilterTree(values: {
  executionModes: readonly string[];
  kinds: readonly string[];
  lifecycles: readonly string[];
}): FilterGroup<ToolFilterProperty> {
  const children: FilterCondition<ToolFilterProperty>[] = [];
  for (const [property, selected] of [
    ["kind", values.kinds],
    ["lifecycle", values.lifecycles],
    ["execution_mode", values.executionModes],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `tools-main-filter-${property}`,
        operator: normalizeFilterOperator(
          "is",
          "multi-select",
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
  tree: FilterGroup<ToolFilterProperty>,
  property: ToolFilterProperty,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function compareTools(
  left: ToolRecord,
  right: ToolRecord,
  field: ToolSortField,
): number {
  if (field === "updated_at") {
    return toTimestamp(left.updatedAt) - toTimestamp(right.updatedAt);
  }
  const leftValue = field === "display_name" ? left.displayName : left[field];
  const rightValue =
    field === "display_name" ? right.displayName : right[field];
  return String(leftValue).localeCompare(String(rightValue), undefined, {
    sensitivity: "base",
  });
}

function appendValues(
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
  return knownValues.filter((value) => values.includes(value));
}

function toTimestamp(value: string | undefined): number {
  const timestamp = value === undefined ? Number.NaN : Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function hasToolsFilters(query: ToolCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

export {
  applyToolsQuery,
  buildToolsSearchParams,
  DEFAULT_TOOLS_QUERY,
  hasToolsFilters,
  parseToolsQuery,
};
