import {
  CONTACTS_PAGE_SIZE,
  CONTACT_LIFECYCLES,
  CONTACT_SORT_DIRECTIONS,
  CONTACT_SORT_FIELDS,
  type ContactCollectionQuery,
  type ContactFilterProperty,
  type ContactLifecycle,
  type ContactListApiQuery,
} from "@/features/contacts/contacts.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "contact-main-filters";

const DEFAULT_CONTACT_QUERY: ContactCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<ContactFilterProperty>(FILTER_ROOT_ID),
  limit: CONTACTS_PAGE_SIZE,
  page: 1,
  search: "",
  sortBy: "updated_at",
};

function parseContactCollectionQuery(
  searchParams: URLSearchParams,
): ContactCollectionQuery {
  const lifecycles = parseKnownValues(
    searchParams.getAll("lifecycle"),
    CONTACT_LIFECYCLES,
  );
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), CONTACT_SORT_DIRECTIONS) ??
      DEFAULT_CONTACT_QUERY.direction,
    filters: createFilterTree(lifecycles),
    limit: CONTACTS_PAGE_SIZE,
    page: parsePage(searchParams.get("page")),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), CONTACT_SORT_FIELDS) ??
      DEFAULT_CONTACT_QUERY.sortBy,
  };
}

function buildContactCollectionSearchParams(
  query: ContactCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  for (const lifecycle of CONTACT_LIFECYCLES) {
    if (filterValues(query.filters).includes(lifecycle)) {
      params.append("lifecycle", lifecycle);
    }
  }
  if (query.sortBy !== DEFAULT_CONTACT_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_CONTACT_QUERY.direction) {
    params.set("direction", query.direction);
  }
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}

function toContactListApiQuery(
  query: ContactCollectionQuery,
): ContactListApiQuery {
  const lifecycles = parseKnownValues(
    filterValues(query.filters),
    CONTACT_LIFECYCLES,
  );
  return {
    lifecycle: lifecycles.length === 0 ? undefined : lifecycles,
    limit: query.limit,
    page: query.page,
    search: query.search || undefined,
    sort_by: query.sortBy,
    sort_direction: query.direction,
  };
}

function hasContactCollectionFilters(query: ContactCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function createFilterTree(
  lifecycles: readonly ContactLifecycle[],
): FilterGroup<ContactFilterProperty> {
  const children: FilterCondition<ContactFilterProperty>[] = [];
  if (lifecycles.length > 0) {
    children.push({
      id: "contact-main-filter-lifecycle",
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

function filterValues(
  tree: FilterGroup<ContactFilterProperty>,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === "lifecycle",
  );
  return condition?.type === "condition" ? condition.values : [];
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
  buildContactCollectionSearchParams,
  DEFAULT_CONTACT_QUERY,
  hasContactCollectionFilters,
  parseContactCollectionQuery,
  toContactListApiQuery,
};
