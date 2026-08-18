import type { FilterUiSchema } from "@/components/filters";
import {
  CAMPAIGN_CHANNELS,
  CAMPAIGN_STATUSES,
} from "@/features/campaigns/campaigns-list-controls";
import type {
  Campaign,
  CampaignCollectionQuery,
  CampaignFilterProperty,
  CampaignSortDirection,
  CampaignSortField,
} from "@/features/campaigns/campaigns.types";
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
] as const satisfies readonly CampaignSortDirection[];
const SORTS = [
  "name",
  "progress",
  "status",
  "updated_at",
] as const satisfies readonly CampaignSortField[];

const DEFAULT_CAMPAIGN_QUERY: CampaignCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<CampaignFilterProperty>(
    "campaigns-main-filters",
  ),
  search: "",
  sortBy: "updated_at",
};

function parseCampaignQuery(params: URLSearchParams): CampaignCollectionQuery {
  return {
    direction:
      known(params.get("direction"), DIRECTIONS) ??
      DEFAULT_CAMPAIGN_QUERY.direction,
    filters: tree([
      ["status", knownMany(params.getAll("status"), CAMPAIGN_STATUSES)],
      ["channel", knownMany(params.getAll("channel"), CAMPAIGN_CHANNELS)],
    ]),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy: known(params.get("sort"), SORTS) ?? DEFAULT_CAMPAIGN_QUERY.sortBy,
  };
}

function buildCampaignSearchParams(
  query: CampaignCollectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  if (query.sortBy !== DEFAULT_CAMPAIGN_QUERY.sortBy)
    params.set("sort", query.sortBy);
  if (query.direction !== DEFAULT_CAMPAIGN_QUERY.direction)
    params.set("direction", query.direction);
  append(params, "status", values(query.filters, "status"), CAMPAIGN_STATUSES);
  append(
    params,
    "channel",
    values(query.filters, "channel"),
    CAMPAIGN_CHANNELS,
  );
  return params;
}

function applyCampaignQuery(
  items: readonly Campaign[],
  query: CampaignCollectionQuery,
  schema: FilterUiSchema<Campaign, CampaignFilterProperty>,
): Campaign[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [item.name, item.description ?? "", item.id]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort(
    (left, right) =>
      directed(compare(left, right, query.sortBy), query.direction) ||
      left.id.localeCompare(right.id),
  );
}

function hasCampaignFilters(query: CampaignCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function tree(
  entries: readonly (readonly [CampaignFilterProperty, readonly string[]])[],
): FilterGroup<CampaignFilterProperty> {
  const children: FilterCondition<CampaignFilterProperty>[] = entries
    .filter(([, selected]) => selected.length > 0)
    .map(([property, selected]) => ({
      id: `campaigns-main-filter-${property}`,
      operator: normalizeFilterOperator("is", "multi-select", selected.length),
      property,
      type: "condition",
      values: [...selected],
    }));
  return { children, id: "campaigns-main-filters", op: "and", type: "group" };
}

function values(
  group: FilterGroup<CampaignFilterProperty>,
  property: CampaignFilterProperty,
): readonly string[] {
  const node = group.children.find(
    (child) => child.type === "condition" && child.property === property,
  );
  return node?.type === "condition" ? node.values : [];
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
function directed(value: number, direction: CampaignSortDirection): number {
  return direction === "asc" ? value : -value;
}
function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}
function compare(
  left: Campaign,
  right: Campaign,
  field: CampaignSortField,
): number {
  if (field === "name") return left.name.localeCompare(right.name);
  if (field === "status") return left.status.localeCompare(right.status);
  if (field === "progress")
    return (
      (left.completedContacts + left.failedContacts) /
        Math.max(1, left.totalContacts) -
      (right.completedContacts + right.failedContacts) /
        Math.max(1, right.totalContacts)
    );
  return timestamp(left.updatedAt) - timestamp(right.updatedAt);
}

export {
  applyCampaignQuery,
  buildCampaignSearchParams,
  DEFAULT_CAMPAIGN_QUERY,
  hasCampaignFilters,
  parseCampaignQuery,
};
