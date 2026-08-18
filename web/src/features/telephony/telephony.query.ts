import type { FilterUiSchema } from "@/components/filters";
import {
  CALL_DIRECTIONS,
  CALL_STATUSES,
  PHONE_STATUSES,
  PROVIDERS,
} from "@/features/telephony/telephony-list-controls";
import type {
  CallCollectionQuery,
  CallFilterProperty,
  CallSortField,
  PhoneNumber,
  PhoneNumberCollectionQuery,
  PhoneNumberFilterProperty,
  PhoneNumberSortField,
  TelephonyCall,
  TelephonySortDirection,
} from "@/features/telephony/telephony.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly TelephonySortDirection[];
const PHONE_SORTS = [
  "label",
  "number",
  "status",
  "updated_at",
] as const satisfies readonly PhoneNumberSortField[];
const CALL_SORTS = [
  "duration",
  "provider",
  "started_at",
  "status",
] as const satisfies readonly CallSortField[];

const DEFAULT_PHONE_NUMBER_QUERY: PhoneNumberCollectionQuery = {
  direction: "asc",
  filters: createEmptyFilterGroup<PhoneNumberFilterProperty>(
    "telephony-numbers-main-filters",
  ),
  search: "",
  sortBy: "number",
};

const DEFAULT_CALL_QUERY: CallCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<CallFilterProperty>(
    "telephony-calls-main-filters",
  ),
  search: "",
  sortBy: "started_at",
};

function parsePhoneNumberQuery(
  params: URLSearchParams,
): PhoneNumberCollectionQuery {
  return {
    direction:
      known(params.get("direction"), DIRECTIONS) ??
      DEFAULT_PHONE_NUMBER_QUERY.direction,
    filters: tree("telephony-numbers", [
      ["status", knownMany(params.getAll("status"), PHONE_STATUSES)],
      ["provider", knownMany(params.getAll("provider"), PROVIDERS)],
    ]),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      known(params.get("sort"), PHONE_SORTS) ??
      DEFAULT_PHONE_NUMBER_QUERY.sortBy,
  };
}

function buildPhoneNumberSearchParams(
  query: PhoneNumberCollectionQuery,
): URLSearchParams {
  const params = baseParams(query, DEFAULT_PHONE_NUMBER_QUERY);
  append(params, "status", values(query.filters, "status"), PHONE_STATUSES);
  append(params, "provider", values(query.filters, "provider"), PROVIDERS);
  return params;
}

function applyPhoneNumberQuery(
  items: readonly PhoneNumber[],
  query: PhoneNumberCollectionQuery,
  schema: FilterUiSchema<PhoneNumber, PhoneNumberFilterProperty>,
): PhoneNumber[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [
            item.number,
            item.label ?? "",
            item.provider,
            item.providerReference ?? "",
            item.id,
          ]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort(
    (left, right) =>
      directed(
        comparePhoneNumbers(left, right, query.sortBy),
        query.direction,
      ) || left.id.localeCompare(right.id),
  );
}

function parseCallQuery(params: URLSearchParams): CallCollectionQuery {
  return {
    direction:
      known(params.get("direction"), DIRECTIONS) ??
      DEFAULT_CALL_QUERY.direction,
    filters: tree("telephony-calls", [
      ["status", knownMany(params.getAll("status"), CALL_STATUSES)],
      ["direction", knownMany(params.getAll("direction"), CALL_DIRECTIONS)],
      ["provider", knownMany(params.getAll("provider"), PROVIDERS)],
    ]),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy: known(params.get("sort"), CALL_SORTS) ?? DEFAULT_CALL_QUERY.sortBy,
  };
}

function buildCallSearchParams(query: CallCollectionQuery): URLSearchParams {
  const params = baseParams(query, DEFAULT_CALL_QUERY);
  append(params, "status", values(query.filters, "status"), CALL_STATUSES);
  append(
    params,
    "direction",
    values(query.filters, "direction"),
    CALL_DIRECTIONS,
  );
  append(params, "provider", values(query.filters, "provider"), PROVIDERS);
  return params;
}

function applyCallQuery(
  items: readonly TelephonyCall[],
  query: CallCollectionQuery,
  schema: FilterUiSchema<TelephonyCall, CallFilterProperty>,
): TelephonyCall[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [
            item.fromNumber ?? "",
            item.toNumber ?? "",
            item.callSid ?? "",
            item.provider,
            item.id,
          ]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort(
    (left, right) =>
      directed(compareCalls(left, right, query.sortBy), query.direction) ||
      left.id.localeCompare(right.id),
  );
}

function hasPhoneNumberFilters(query: PhoneNumberCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function hasCallFilters(query: CallCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function tree<Property extends string>(
  prefix: string,
  entries: readonly (readonly [Property, readonly string[]])[],
): FilterGroup<Property> {
  const children: FilterCondition<Property>[] = entries
    .filter(([, selected]) => selected.length > 0)
    .map(([property, selected]) => ({
      id: `${prefix}-main-filter-${property}`,
      operator: normalizeFilterOperator("is", "multi-select", selected.length),
      property,
      type: "condition",
      values: [...selected],
    }));
  return { children, id: `${prefix}-main-filters`, op: "and", type: "group" };
}

function values<Property extends string>(
  group: FilterGroup<Property>,
  property: Property,
): readonly string[] {
  const node = group.children.find(
    (child) => child.type === "condition" && child.property === property,
  );
  return node?.type === "condition" ? node.values : [];
}

function baseParams<
  Query extends { direction: string; search: string; sortBy: string },
>(query: Query, defaults: Query): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  if (query.sortBy !== defaults.sortBy) params.set("sort", query.sortBy);
  if (query.direction !== defaults.direction)
    params.set("direction", query.direction);
  return params;
}

function append(
  params: URLSearchParams,
  key: string,
  selected: readonly string[],
  knownValues: readonly string[],
): void {
  for (const value of knownValues)
    if (selected.includes(value)) params.append(key, value);
}

function known<Value extends string>(
  value: string | null,
  knownValues: readonly Value[],
): Value | null {
  return value !== null && knownValues.includes(value as Value)
    ? (value as Value)
    : null;
}

function knownMany<Value extends string>(
  selected: readonly string[],
  knownValues: readonly Value[],
): Value[] {
  return knownValues.filter((value) => selected.includes(value));
}

function directed(value: number, direction: TelephonySortDirection): number {
  return direction === "asc" ? value : -value;
}

function timestamp(value: string | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function comparePhoneNumbers(
  left: PhoneNumber,
  right: PhoneNumber,
  field: PhoneNumberSortField,
): number {
  if (field === "number") return left.number.localeCompare(right.number);
  if (field === "label")
    return (left.label ?? "").localeCompare(right.label ?? "");
  if (field === "status") return left.status.localeCompare(right.status);
  return timestamp(left.updatedAt) - timestamp(right.updatedAt);
}

function compareCalls(
  left: TelephonyCall,
  right: TelephonyCall,
  field: CallSortField,
): number {
  if (field === "duration")
    return (left.durationSeconds ?? 0) - (right.durationSeconds ?? 0);
  if (field === "provider") return left.provider.localeCompare(right.provider);
  if (field === "status") return left.status.localeCompare(right.status);
  return timestamp(left.startedAt) - timestamp(right.startedAt);
}

export {
  applyCallQuery,
  applyPhoneNumberQuery,
  buildCallSearchParams,
  buildPhoneNumberSearchParams,
  DEFAULT_CALL_QUERY,
  DEFAULT_PHONE_NUMBER_QUERY,
  hasCallFilters,
  hasPhoneNumberFilters,
  parseCallQuery,
  parsePhoneNumberQuery,
};
