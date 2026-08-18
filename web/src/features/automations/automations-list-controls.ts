import { CalendarClock, CircleGauge, GitBranch, Type } from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  ScheduleFilterProperty,
  ScheduleRecord,
  ScheduleSortField,
} from "@/features/automations/automations.types";

const AUTOMATION_SORT_OPTIONS = [
  { icon: CalendarClock, label: "Next run", value: "next_at" },
  { icon: CalendarClock, label: "Last run", value: "last_fired_at" },
  { icon: Type, label: "Name", value: "name" },
  { icon: GitBranch, label: "Lifecycle", value: "lifecycle" },
] as const satisfies readonly SortOption<ScheduleSortField>[];

const AUTOMATION_FILTER_SCHEMA: FilterUiSchema<
  ScheduleRecord,
  ScheduleFilterProperty
> = [
  {
    accessor: (schedule) => schedule.enabled,
    icon: CircleGauge,
    label: "Enabled",
    operators: ["is"],
    options: [
      { label: "Yes", value: "true" },
      { label: "No", value: "false" },
    ],
    property: "enabled",
    valueType: "single-select",
  },
  {
    accessor: (schedule) => schedule.lifecycle,
    icon: GitBranch,
    label: "Lifecycle",
    operators: ["is"],
    options: [
      { label: "Published", value: "published" },
      { label: "Withdrawn", value: "withdrawn" },
    ],
    property: "lifecycle",
    valueType: "multi-select",
  },
  {
    accessor: (schedule) => schedule.misfire_policy,
    icon: CalendarClock,
    label: "Missed runs",
    operators: ["is"],
    options: [
      { label: "Run latest once", value: "coalesce" },
      { label: "Run every missed occurrence", value: "fire_all" },
    ],
    property: "misfire_policy",
    valueType: "multi-select",
  },
];

export { AUTOMATION_FILTER_SCHEMA, AUTOMATION_SORT_OPTIONS };
