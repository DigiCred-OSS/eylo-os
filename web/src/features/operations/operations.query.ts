import type { FilterUiSchema } from "@/components/filters";
import type {
  AgentRun,
  AgentRunCollectionQuery,
  AgentRunFilterProperty,
  AgentRunSortField,
  OperationSortDirection,
  VoiceSession,
  VoiceSessionCollectionQuery,
  VoiceSessionFilterProperty,
  VoiceSessionSortField,
} from "@/features/operations/operations.types";
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
] as const satisfies readonly OperationSortDirection[];
const RUN_SORTS = [
  "created_at",
  "goal",
  "lifecycle",
  "updated_at",
] as const satisfies readonly AgentRunSortField[];
const RUN_LIFECYCLES = [
  "queued",
  "running",
  "waiting_for_input",
  "waiting_for_approval",
  "completed",
  "failed",
  "cancelled",
] as const;
const RUN_OUTCOMES = [
  "achieved",
  "unachievable",
  "failed",
  "cancelled",
  "exhausted",
] as const;
const RUN_ORIGINS = ["message", "schedule_occurrence", "objective"] as const;
const VOICE_SORTS = [
  "started_at",
  "duration",
  "status",
  "segments",
] as const satisfies readonly VoiceSessionSortField[];
const VOICE_STATUSES = ["active", "completed", "failed"] as const;
const VOICE_RUNTIMES = [
  "browser_decomposed",
  "browser_realtime",
  "telephony",
] as const;
const CANONICAL_STATES = [
  "not_run",
  "clean",
  "redacted",
  "failed",
  "no_storage",
] as const;

const DEFAULT_AGENT_RUN_QUERY: AgentRunCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<AgentRunFilterProperty>(
    "agent-runs-main-filters",
  ),
  search: "",
  sortBy: "created_at",
};
const DEFAULT_VOICE_SESSION_QUERY: VoiceSessionCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<VoiceSessionFilterProperty>(
    "voice-sessions-main-filters",
  ),
  search: "",
  sortBy: "started_at",
};

function parseAgentRunQuery(params: URLSearchParams): AgentRunCollectionQuery {
  return {
    direction:
      known(params.get("direction"), DIRECTIONS) ??
      DEFAULT_AGENT_RUN_QUERY.direction,
    filters: tree("agent-runs", [
      ["lifecycle", knownMany(params.getAll("lifecycle"), RUN_LIFECYCLES)],
      ["outcome", knownMany(params.getAll("outcome"), RUN_OUTCOMES)],
      ["origin", knownMany(params.getAll("origin"), RUN_ORIGINS)],
    ]),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      known(params.get("sort"), RUN_SORTS) ?? DEFAULT_AGENT_RUN_QUERY.sortBy,
  };
}

function buildAgentRunSearchParams(
  query: AgentRunCollectionQuery,
): URLSearchParams {
  const params = baseParams(
    query.search,
    query.sortBy,
    query.direction,
    DEFAULT_AGENT_RUN_QUERY,
  );
  append(
    params,
    "lifecycle",
    values(query.filters, "lifecycle"),
    RUN_LIFECYCLES,
  );
  append(params, "outcome", values(query.filters, "outcome"), RUN_OUTCOMES);
  append(params, "origin", values(query.filters, "origin"), RUN_ORIGINS);
  return params;
}

function applyAgentRunQuery(
  items: readonly AgentRun[],
  query: AgentRunCollectionQuery,
  schema: FilterUiSchema<AgentRun, AgentRunFilterProperty>,
): AgentRun[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [item.goal, item.id, item.agent_id, item.failure_summary ?? ""]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort(
    (left, right) =>
      directed(compareRuns(left, right, query.sortBy), query.direction) ||
      left.id.localeCompare(right.id),
  );
}

function parseVoiceSessionQuery(
  params: URLSearchParams,
): VoiceSessionCollectionQuery {
  return {
    direction:
      known(params.get("direction"), DIRECTIONS) ??
      DEFAULT_VOICE_SESSION_QUERY.direction,
    filters: tree("voice-sessions", [
      ["status", knownMany(params.getAll("status"), VOICE_STATUSES)],
      ["runtime", knownMany(params.getAll("runtime"), VOICE_RUNTIMES)],
      [
        "canonical_state",
        knownMany(params.getAll("canonical"), CANONICAL_STATES),
      ],
    ]),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      known(params.get("sort"), VOICE_SORTS) ??
      DEFAULT_VOICE_SESSION_QUERY.sortBy,
  };
}

function buildVoiceSessionSearchParams(
  query: VoiceSessionCollectionQuery,
): URLSearchParams {
  const params = baseParams(
    query.search,
    query.sortBy,
    query.direction,
    DEFAULT_VOICE_SESSION_QUERY,
  );
  append(params, "status", values(query.filters, "status"), VOICE_STATUSES);
  append(params, "runtime", values(query.filters, "runtime"), VOICE_RUNTIMES);
  append(
    params,
    "canonical",
    values(query.filters, "canonical_state"),
    CANONICAL_STATES,
  );
  return params;
}

function applyVoiceSessionQuery(
  items: readonly VoiceSession[],
  query: VoiceSessionCollectionQuery,
  schema: FilterUiSchema<VoiceSession, VoiceSessionFilterProperty>,
): VoiceSession[] {
  const term = query.search.toLocaleLowerCase();
  const searched =
    term === ""
      ? [...items]
      : items.filter((item) =>
          [
            item.id,
            item.sessionId,
            item.conversationId,
            item.agentId ?? "",
            item.transport,
            item.sttVendor ?? "",
            item.ttsVendor ?? "",
            item.realtimeVendor ?? "",
          ]
            .join(" ")
            .toLocaleLowerCase()
            .includes(term),
        );
  return applyFilters(searched, query.filters, schema).sort(
    (left, right) =>
      directed(compareVoice(left, right, query.sortBy), query.direction) ||
      left.id.localeCompare(right.id),
  );
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
>(
  search: string,
  sort: string,
  direction: string,
  defaults: Query,
): URLSearchParams {
  const params = new URLSearchParams();
  if (search !== "") params.set("q", search);
  if (sort !== defaults.sortBy) params.set("sort", sort);
  if (direction !== defaults.direction) params.set("direction", direction);
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
function directed(value: number, direction: OperationSortDirection): number {
  return direction === "asc" ? value : -value;
}
function timestamp(value: string): number {
  const time = Date.parse(value);
  return Number.isNaN(time) ? 0 : time;
}
function compareRuns(
  left: AgentRun,
  right: AgentRun,
  field: AgentRunSortField,
): number {
  if (field === "goal") return left.goal.localeCompare(right.goal);
  if (field === "lifecycle")
    return left.lifecycle.localeCompare(right.lifecycle);
  return timestamp(left[field]) - timestamp(right[field]);
}
function compareVoice(
  left: VoiceSession,
  right: VoiceSession,
  field: VoiceSessionSortField,
): number {
  if (field === "duration")
    return (left.durationMs ?? 0) - (right.durationMs ?? 0);
  if (field === "segments") return left.segmentCount - right.segmentCount;
  if (field === "status") return left.status.localeCompare(right.status);
  return timestamp(left.startedAt) - timestamp(right.startedAt);
}
function hasFilters(query: {
  filters: FilterGroup<string>;
  search: string;
}): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

export {
  applyAgentRunQuery,
  applyVoiceSessionQuery,
  buildAgentRunSearchParams,
  buildVoiceSessionSearchParams,
  DEFAULT_AGENT_RUN_QUERY,
  DEFAULT_VOICE_SESSION_QUERY,
  hasFilters,
  parseAgentRunQuery,
  parseVoiceSessionQuery,
};
