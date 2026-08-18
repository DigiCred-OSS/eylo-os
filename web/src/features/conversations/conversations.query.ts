import {
  CONVERSATION_CHANNELS,
  CONVERSATION_SORT_DIRECTIONS,
  CONVERSATION_SORT_FIELDS,
  CONVERSATION_STATUSES,
  CONVERSATIONS_PAGE_SIZE,
  type ConversationChannel,
  type ConversationCollectionQuery,
  type ConversationFilterProperty,
  type ConversationListApiQuery,
  type ConversationStatus,
} from "@/features/conversations/conversations.types";
import {
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "conversation-main-filters";
const PAGE_SIZES = [20, 50, 100] as const;

const DEFAULT_CONVERSATION_QUERY: ConversationCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<ConversationFilterProperty>(FILTER_ROOT_ID),
  limit: CONVERSATIONS_PAGE_SIZE,
  page: 1,
  search: "",
  sortBy: "updated_at",
};

function parseConversationCollectionQuery(
  searchParams: URLSearchParams,
): ConversationCollectionQuery {
  return {
    direction:
      parseKnownValue(
        searchParams.get("direction"),
        CONVERSATION_SORT_DIRECTIONS,
      ) ?? DEFAULT_CONVERSATION_QUERY.direction,
    filters: createFilterTree({
      channels: parseKnownValues(
        searchParams.getAll("channel"),
        CONVERSATION_CHANNELS,
      ),
      statuses: parseKnownValues(
        searchParams.getAll("status"),
        CONVERSATION_STATUSES,
      ),
    }),
    limit:
      parseKnownNumber(searchParams.get("limit"), PAGE_SIZES) ??
      DEFAULT_CONVERSATION_QUERY.limit,
    page: parsePositiveInteger(searchParams.get("page")) ?? 1,
    search: searchParams.get("q")?.trim().slice(0, 200) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), CONVERSATION_SORT_FIELDS) ??
      DEFAULT_CONVERSATION_QUERY.sortBy,
  };
}

function buildConversationCollectionSearchParams(
  query: ConversationCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") {
    params.set("q", query.search);
  }
  appendKnownValues(
    params,
    "status",
    filterValues(query.filters, "status"),
    CONVERSATION_STATUSES,
  );
  appendKnownValues(
    params,
    "channel",
    filterValues(query.filters, "channel"),
    CONVERSATION_CHANNELS,
  );
  if (query.sortBy !== DEFAULT_CONVERSATION_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_CONVERSATION_QUERY.direction) {
    params.set("direction", query.direction);
  }
  if (query.page !== 1) {
    params.set("page", String(query.page));
  }
  if (query.limit !== DEFAULT_CONVERSATION_QUERY.limit) {
    params.set("limit", String(query.limit));
  }
  return params;
}

function toConversationListApiQuery(
  query: ConversationCollectionQuery,
): ConversationListApiQuery {
  const statuses = filterValues(
    query.filters,
    "status",
  ) as ConversationStatus[];
  const channels = filterValues(
    query.filters,
    "channel",
  ) as ConversationChannel[];
  return {
    channel: channels.length === 0 ? undefined : channels,
    direction: query.direction,
    limit: query.limit,
    page: query.page,
    q: query.search === "" ? undefined : query.search,
    sort: query.sortBy,
    status: statuses.length === 0 ? undefined : statuses,
  };
}

function hasConversationCollectionFilters(
  query: ConversationCollectionQuery,
): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function createFilterTree(values: {
  channels: readonly ConversationChannel[];
  statuses: readonly ConversationStatus[];
}): FilterGroup<ConversationFilterProperty> {
  const children: FilterCondition<ConversationFilterProperty>[] = [];
  for (const [property, selected] of [
    ["status", values.statuses],
    ["channel", values.channels],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `conversation-main-filter-${property}`,
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
  tree: FilterGroup<ConversationFilterProperty>,
  property: ConversationFilterProperty,
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
  buildConversationCollectionSearchParams,
  DEFAULT_CONVERSATION_QUERY,
  hasConversationCollectionFilters,
  parseConversationCollectionQuery,
  toConversationListApiQuery,
};
