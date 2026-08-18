import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type ToolRecord = components["schemas"]["ToolResponseSchema"];
type ToolCapability = components["schemas"]["Capability"];
type ToolSource = "managed" | "system" | "provider";
type ToolFilterProperty = "execution_mode" | "kind" | "lifecycle";
type ToolSortField = "display_name" | "kind" | "lifecycle" | "updated_at";
type ToolSortDirection = "asc" | "desc";

interface ToolCollectionQuery {
  capability: ToolCapability;
  direction: ToolSortDirection;
  filters: FilterGroup<ToolFilterProperty>;
  search: string;
  sortBy: ToolSortField;
  source: ToolSource;
}

export type {
  ToolCapability,
  ToolCollectionQuery,
  ToolFilterProperty,
  ToolRecord,
  ToolSortDirection,
  ToolSortField,
  ToolSource,
};
