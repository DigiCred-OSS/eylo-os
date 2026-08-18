import {
  CalendarClock,
  CircleGauge,
  GitBranch,
  Layers3,
  Type,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  ToolFilterProperty,
  ToolRecord,
  ToolSortField,
} from "@/features/tools/tools.types";

const TOOL_SORT_OPTIONS = [
  { icon: Type, label: "Name", value: "display_name" },
  { icon: Layers3, label: "Kind", value: "kind" },
  { icon: GitBranch, label: "Lifecycle", value: "lifecycle" },
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
] as const satisfies readonly SortOption<ToolSortField>[];

const TOOL_FILTER_SCHEMA: FilterUiSchema<ToolRecord, ToolFilterProperty> = [
  {
    accessor: (tool) => tool.kind,
    icon: Layers3,
    label: "Kind",
    operators: ["is"],
    options: [
      { label: "Local", value: "LOCAL" },
      { label: "System", value: "SYSTEM" },
      { label: "MCP", value: "MCP" },
      { label: "Curated", value: "CURATED" },
    ],
    property: "kind",
    valueType: "multi-select",
  },
  {
    accessor: (tool) => tool.lifecycle,
    icon: GitBranch,
    label: "Lifecycle",
    operators: ["is"],
    options: [
      { label: "Draft", value: "draft" },
      { label: "Published", value: "published" },
      { label: "Withdrawn", value: "withdrawn" },
      { label: "Archived", value: "archived" },
    ],
    property: "lifecycle",
    valueType: "multi-select",
  },
  {
    accessor: (tool) => tool.executionMode,
    icon: CircleGauge,
    label: "Execution mode",
    operators: ["is"],
    options: [
      { label: "Automatic", value: "auto" },
      { label: "Requires approval", value: "requires_approval" },
      { label: "Disabled", value: "disabled" },
    ],
    property: "execution_mode",
    valueType: "multi-select",
  },
];

const CATALOG_TOOL_FILTER_SCHEMA = TOOL_FILTER_SCHEMA.filter(
  (definition) => definition.property !== "lifecycle",
);

const CATALOG_TOOL_SORT_OPTIONS = TOOL_SORT_OPTIONS.filter(
  (option) => option.value !== "lifecycle" && option.value !== "updated_at",
);

export {
  CATALOG_TOOL_FILTER_SCHEMA,
  CATALOG_TOOL_SORT_OPTIONS,
  TOOL_FILTER_SCHEMA,
  TOOL_SORT_OPTIONS,
};
