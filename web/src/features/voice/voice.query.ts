import type { FilterUiSchema } from "@/components/filters";
import type {
  VoiceCollectionQuery,
  VoiceConfigRecord,
  VoiceFilterProperty,
  VoiceRuntimeMode,
  VoiceSortDirection,
  VoiceSortField,
} from "@/features/voice/voice.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
} from "@/lib/filters";

const FILTER_ROOT_ID = "voice-main-filters";
const SORT_FIELDS = [
  "name",
  "revision",
  "updated_at",
] as const satisfies readonly VoiceSortField[];
const SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly VoiceSortDirection[];
const RUNTIME_MODES = [
  "decomposed",
  "realtime",
] as const satisfies readonly VoiceRuntimeMode[];
const BOOLEAN_VALUES = ["true", "false"] as const;

const DEFAULT_VOICE_QUERY: VoiceCollectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<VoiceFilterProperty>(FILTER_ROOT_ID),
  search: "",
  sortBy: "updated_at",
};

function parseVoiceCollectionQuery(
  searchParams: URLSearchParams,
): VoiceCollectionQuery {
  return {
    direction:
      parseKnownValue(searchParams.get("direction"), SORT_DIRECTIONS) ??
      DEFAULT_VOICE_QUERY.direction,
    filters: createFilterTree({
      audioStorage: parseKnownValues(
        searchParams.getAll("audio_storage"),
        BOOLEAN_VALUES,
      ),
      runtimes: parseKnownValues(searchParams.getAll("runtime"), RUNTIME_MODES),
    }),
    search: searchParams.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(searchParams.get("sort"), SORT_FIELDS) ??
      DEFAULT_VOICE_QUERY.sortBy,
  };
}

function buildVoiceCollectionSearchParams(
  query: VoiceCollectionQuery,
): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (query.search !== "") {
    searchParams.set("q", query.search);
  }
  appendKnownValues(
    searchParams,
    "runtime",
    filterValues(query.filters, "runtime"),
    RUNTIME_MODES,
  );
  appendKnownValues(
    searchParams,
    "audio_storage",
    filterValues(query.filters, "audio_storage"),
    BOOLEAN_VALUES,
  );
  if (query.sortBy !== DEFAULT_VOICE_QUERY.sortBy) {
    searchParams.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_VOICE_QUERY.direction) {
    searchParams.set("direction", query.direction);
  }
  return searchParams;
}

function applyVoiceCollectionQuery(
  items: readonly VoiceConfigRecord[],
  query: VoiceCollectionQuery,
  schema: FilterUiSchema<VoiceConfigRecord, VoiceFilterProperty>,
): VoiceConfigRecord[] {
  const search = query.search.toLocaleLowerCase();
  const searched =
    search === ""
      ? [...items]
      : items.filter((item) =>
          [item.name, item.description ?? ""]
            .join(" ")
            .toLocaleLowerCase()
            .includes(search),
        );
  const filtered = applyFilters(searched, query.filters, schema);
  return filtered.sort((left, right) => {
    const compared = compareVoiceConfigs(left, right, query.sortBy);
    const directed = query.direction === "asc" ? compared : -compared;
    return directed !== 0 ? directed : left.id.localeCompare(right.id);
  });
}

function voiceRuntimeMode(config: VoiceConfigRecord): VoiceRuntimeMode {
  return config.config.realtime_provider_config_id === null ||
    config.config.realtime_provider_config_id === undefined
    ? "decomposed"
    : "realtime";
}

function createFilterTree(values: {
  audioStorage: readonly string[];
  runtimes: readonly VoiceRuntimeMode[];
}): FilterGroup<VoiceFilterProperty> {
  const children: FilterCondition<VoiceFilterProperty>[] = [];
  for (const [property, selected] of [
    ["runtime", values.runtimes],
    ["audio_storage", values.audioStorage],
  ] as const) {
    if (selected.length > 0) {
      children.push({
        id: `voice-main-filter-${property}`,
        operator: normalizeFilterOperator(
          "is",
          property === "audio_storage" ? "single-select" : "multi-select",
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
  tree: FilterGroup<VoiceFilterProperty>,
  property: VoiceFilterProperty,
): readonly string[] {
  const condition = tree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function compareVoiceConfigs(
  left: VoiceConfigRecord,
  right: VoiceConfigRecord,
  field: VoiceSortField,
): number {
  if (field === "revision") {
    return left.revision - right.revision;
  }
  if (field === "updated_at") {
    return toTimestamp(left.updated_at) - toTimestamp(right.updated_at);
  }
  return left.name.localeCompare(right.name, undefined, {
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

function hasVoiceCollectionFilters(query: VoiceCollectionQuery): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

export {
  applyVoiceCollectionQuery,
  buildVoiceCollectionSearchParams,
  DEFAULT_VOICE_QUERY,
  hasVoiceCollectionFilters,
  parseVoiceCollectionQuery,
  voiceRuntimeMode,
};
