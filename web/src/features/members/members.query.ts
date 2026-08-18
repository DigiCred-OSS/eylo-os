import {
  MEMBERS_PAGE_SIZE,
  MEMBER_SORT_DIRECTIONS,
  MEMBER_SORT_FIELDS,
  MEMBER_STATUSES,
  type MemberCollectionQuery,
  type MemberFilterProperty,
  type MemberListApiQuery,
  type MemberStatus,
} from "@/features/members/members.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "member-main-filters";

const DEFAULT_MEMBER_QUERY: MemberCollectionQuery = {
  direction: "asc",
  filters: createEmptyFilterGroup<MemberFilterProperty>(FILTER_ROOT_ID),
  limit: MEMBERS_PAGE_SIZE,
  page: 1,
  search: "",
  sortBy: "name",
};

function parseMemberCollectionQuery(
  searchParams: URLSearchParams,
): MemberCollectionQuery {
  const statuses = parseKnownValues(
    searchParams.getAll("status"),
    MEMBER_STATUSES,
  );
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), MEMBER_SORT_DIRECTIONS) ??
      DEFAULT_MEMBER_QUERY.direction,
    filters: createFilterTree(statuses),
    limit: MEMBERS_PAGE_SIZE,
    page: parsePage(searchParams.get("page")),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), MEMBER_SORT_FIELDS) ??
      DEFAULT_MEMBER_QUERY.sortBy,
  };
}

function buildMemberCollectionSearchParams(
  query: MemberCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  for (const status of MEMBER_STATUSES) {
    if (filterValues(query.filters).includes(status)) {
      params.append("status", status);
    }
  }
  if (query.sortBy !== DEFAULT_MEMBER_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_MEMBER_QUERY.direction) {
    params.set("direction", query.direction);
  }
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}

function toMemberListApiQuery(
  query: MemberCollectionQuery,
): MemberListApiQuery {
  const statuses = parseKnownValues(
    filterValues(query.filters),
    MEMBER_STATUSES,
  );
  return {
    limit: query.limit,
    page: query.page,
    search: query.search || undefined,
    sort_by: query.sortBy,
    sort_direction: query.direction,
    status: statuses.length === 0 ? undefined : statuses,
  };
}

function hasMemberCollectionFilters(query: MemberCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function createFilterTree(
  statuses: readonly MemberStatus[],
): FilterGroup<MemberFilterProperty> {
  const children: FilterCondition<MemberFilterProperty>[] = [];
  if (statuses.length > 0) {
    children.push({
      id: "member-main-filter-status",
      operator: normalizeFilterOperator("is", "multi-select", statuses.length),
      property: "status",
      type: "condition",
      values: [...statuses],
    });
  }
  return { children, id: FILTER_ROOT_ID, op: "and", type: "group" };
}

function filterValues(
  tree: FilterGroup<MemberFilterProperty>,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === "status",
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
  buildMemberCollectionSearchParams,
  DEFAULT_MEMBER_QUERY,
  hasMemberCollectionFilters,
  parseMemberCollectionQuery,
  toMemberListApiQuery,
};
