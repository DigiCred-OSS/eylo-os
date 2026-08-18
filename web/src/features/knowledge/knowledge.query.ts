import type { FilterUiSchema } from "@/components/filters";
import type {
  Knowledgebase,
  KnowledgeCollectionQuery,
  KnowledgeFilterProperty,
  KnowledgeScope,
  KnowledgeSortDirection,
  KnowledgeSortField,
  KnowledgeVendor,
} from "@/features/knowledge/knowledge.types";
import {
  KNOWLEDGE_SCOPES,
  KNOWLEDGE_VENDORS,
} from "@/features/knowledge/knowledge.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "knowledge-main-filters";
const SORT_FIELDS = [
  "name",
  "vendor",
  "scope",
  "updated_at",
] as const satisfies readonly KnowledgeSortField[];
const SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly KnowledgeSortDirection[];
const BOOLEAN_VALUES = ["true", "false"] as const;

const DEFAULT_KNOWLEDGE_QUERY: KnowledgeCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<KnowledgeFilterProperty>(FILTER_ROOT_ID),
  search: "",
  sortBy: "updated_at",
};

function parseKnowledgeCollectionQuery(
  searchParams: URLSearchParams,
): KnowledgeCollectionQuery {
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), SORT_DIRECTIONS) ??
      DEFAULT_KNOWLEDGE_QUERY.direction,
    filters: createFilterTree({
      scopes: parseKnownValues(searchParams.getAll("scope"), KNOWLEDGE_SCOPES),
      vendors: parseKnownValues(
        searchParams.getAll("vendor"),
        KNOWLEDGE_VENDORS,
      ),
      writable: parseKnownValues(
        searchParams.getAll("writable"),
        BOOLEAN_VALUES,
      ),
    }),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), SORT_FIELDS) ??
      DEFAULT_KNOWLEDGE_QUERY.sortBy,
  };
}

function buildKnowledgeCollectionSearchParams(
  query: KnowledgeCollectionQuery,
): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (query.search !== "") {
    searchParams.set("q", query.search);
  }
  appendKnownValues(
    searchParams,
    "vendor",
    filterValues(query.filters, "vendor"),
    KNOWLEDGE_VENDORS,
  );
  appendKnownValues(
    searchParams,
    "scope",
    filterValues(query.filters, "scope"),
    KNOWLEDGE_SCOPES,
  );
  appendKnownValues(
    searchParams,
    "writable",
    filterValues(query.filters, "writable"),
    BOOLEAN_VALUES,
  );
  if (query.sortBy !== DEFAULT_KNOWLEDGE_QUERY.sortBy) {
    searchParams.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_KNOWLEDGE_QUERY.direction) {
    searchParams.set("direction", query.direction);
  }
  return searchParams;
}

function applyKnowledgeCollectionQuery(
  items: readonly Knowledgebase[],
  query: KnowledgeCollectionQuery,
  schema: FilterUiSchema<Knowledgebase, KnowledgeFilterProperty>,
): Knowledgebase[] {
  const search = query.search.toLocaleLowerCase();
  const searched =
    search === ""
      ? [...items]
      : items.filter((item) =>
          [item.name, item.slug, item.vendor, item.embedding_model ?? ""]
            .join(" ")
            .toLocaleLowerCase()
            .includes(search),
        );
  const filtered = applyFilters(searched, query.filters, schema);
  return filtered.sort((left, right) => {
    const compared = compareKnowledgebases(left, right, query.sortBy);
    const directed = query.direction === "asc" ? compared : -compared;
    return directed !== 0 ? directed : left.id.localeCompare(right.id);
  });
}

function createFilterTree(values: {
  scopes: readonly KnowledgeScope[];
  vendors: readonly KnowledgeVendor[];
  writable: readonly string[];
}): FilterGroup<KnowledgeFilterProperty> {
  const children: FilterCondition<KnowledgeFilterProperty>[] = [];
  for (const [property, selected] of [
    ["vendor", values.vendors],
    ["scope", values.scopes],
    ["writable", values.writable],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `knowledge-main-filter-${property}`,
        operator: normalizeFilterOperator(
          "is",
          property === "writable" ? "single-select" : "multi-select",
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
  tree: FilterGroup<KnowledgeFilterProperty>,
  property: KnowledgeFilterProperty,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function compareKnowledgebases(
  left: Knowledgebase,
  right: Knowledgebase,
  field: KnowledgeSortField,
): number {
  if (field === "updated_at") {
    return toTimestamp(left.updated_at) - toTimestamp(right.updated_at);
  }
  return left[field].localeCompare(right[field], undefined, {
    sensitivity: "base",
  });
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

function toTimestamp(value: string): number {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function hasKnowledgeCollectionFilters(
  query: KnowledgeCollectionQuery,
): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

export {
  applyKnowledgeCollectionQuery,
  buildKnowledgeCollectionSearchParams,
  DEFAULT_KNOWLEDGE_QUERY,
  hasKnowledgeCollectionFilters,
  parseKnowledgeCollectionQuery,
};
