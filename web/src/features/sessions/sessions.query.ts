import {
  SESSION_PAGE_SIZE,
  USER_SESSION_CHANNELS,
  USER_SESSION_SORT_DIRECTIONS,
  USER_SESSION_SORT_FIELDS,
  USER_SESSION_STATES,
  type SessionCollectionQuery,
  type SessionFilterProperty,
  type UserSessionEntryChannel,
  type UserSessionListApiQuery,
  type UserSessionState,
} from "@/features/sessions/sessions.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "session-main-filters";
const PAGE_SIZES = [20, 50, 100] as const;

const DEFAULT_SESSION_QUERY: SessionCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<SessionFilterProperty>(FILTER_ROOT_ID),
  limit: SESSION_PAGE_SIZE,
  page: 1,
  search: "",
  sortBy: "started_at",
};

function parseSessionCollectionQuery(
  searchParams: URLSearchParams,
): SessionCollectionQuery {
  return {
    direction:
      parseKnownValue(
        searchParams.get("direction"),
        USER_SESSION_SORT_DIRECTIONS,
      ) ?? DEFAULT_SESSION_QUERY.direction,
    filters: createFilterTree({
      channels: parseKnownValues(
        searchParams.getAll("channel"),
        USER_SESSION_CHANNELS,
      ),
      states: parseKnownValues(
        searchParams.getAll("state"),
        USER_SESSION_STATES,
      ),
    }),
    limit:
      parseKnownNumber(searchParams.get("limit"), PAGE_SIZES) ??
      DEFAULT_SESSION_QUERY.limit,
    page: parsePositiveInteger(searchParams.get("page")) ?? 1,
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), USER_SESSION_SORT_FIELDS) ??
      DEFAULT_SESSION_QUERY.sortBy,
  };
}

function buildSessionCollectionSearchParams(
  query: SessionCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") {
    params.set("q", query.search);
  }
  appendKnownValues(
    params,
    "state",
    filterValues(query.filters, "state"),
    USER_SESSION_STATES,
  );
  appendKnownValues(
    params,
    "channel",
    filterValues(query.filters, "channel"),
    USER_SESSION_CHANNELS,
  );
  if (query.sortBy !== DEFAULT_SESSION_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_SESSION_QUERY.direction) {
    params.set("direction", query.direction);
  }
  if (query.page !== 1) {
    params.set("page", String(query.page));
  }
  if (query.limit !== DEFAULT_SESSION_QUERY.limit) {
    params.set("limit", String(query.limit));
  }
  return params;
}

function toUserSessionListApiQuery(
  query: SessionCollectionQuery,
): UserSessionListApiQuery {
  const states = filterValues(query.filters, "state") as UserSessionState[];
  const channels = filterValues(
    query.filters,
    "channel",
  ) as UserSessionEntryChannel[];
  return {
    entry_channel: channels.length === 0 ? undefined : channels,
    limit: query.limit,
    page: query.page,
    search: query.search === "" ? undefined : query.search,
    sort_by: query.sortBy,
    sort_direction: query.direction,
    state: states.length === 0 ? undefined : states,
  };
}

function hasSessionCollectionFilters(query: SessionCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function createFilterTree(values: {
  channels: readonly UserSessionEntryChannel[];
  states: readonly UserSessionState[];
}): FilterGroup<SessionFilterProperty> {
  const children: FilterCondition<SessionFilterProperty>[] = [];
  for (const [property, selected] of [
    ["state", values.states],
    ["channel", values.channels],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `session-main-filter-${property}`,
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
  tree: FilterGroup<SessionFilterProperty>,
  property: SessionFilterProperty,
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

function parseKnownNumber(
  value: string | null,
  knownValues: readonly number[],
): number | null {
  if (value === null) {
    return null;
  }
  const parsed = Number(value);
  return knownValues.includes(parsed) ? parsed : null;
}

function parsePositiveInteger(value: string | null): number | null {
  if (value === null || !/^\d+$/.test(value)) {
    return null;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export {
  buildSessionCollectionSearchParams,
  DEFAULT_SESSION_QUERY,
  hasSessionCollectionFilters,
  parseSessionCollectionQuery,
  toUserSessionListApiQuery,
};
