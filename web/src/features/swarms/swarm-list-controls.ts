import { CalendarDays, CircleDot, Clock3, Type } from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { formatSwarmEnum } from "@/features/swarms/swarm-formatters";
import {
  SWARM_LIFECYCLES,
  type Swarm,
  type SwarmFilterProperty,
  type SwarmSortField,
} from "@/features/swarms/swarms.types";

const SWARM_FILTER_SCHEMA = [
  {
    accessor: (swarm: Swarm) => swarm.lifecycle,
    icon: CircleDot,
    keywords: ["state", "published", "withdrawn", "draft"],
    label: "Lifecycle",
    operators: ["is"],
    options: SWARM_LIFECYCLES.map((lifecycle) => ({
      keywords: [lifecycle],
      label: formatSwarmEnum(lifecycle),
      value: lifecycle,
    })),
    property: "lifecycle",
    valueType: "multi-select",
  },
] as const satisfies FilterUiSchema<Swarm, SwarmFilterProperty>;

const SWARM_SORT_OPTIONS = [
  { icon: Type, label: "Name", value: "name" },
  { icon: CircleDot, label: "Lifecycle", value: "lifecycle" },
  { icon: CalendarDays, label: "Created", value: "created_at" },
  { icon: Clock3, label: "Updated", value: "updated_at" },
] as const satisfies readonly SortOption<SwarmSortField>[];

export { SWARM_FILTER_SCHEMA, SWARM_SORT_OPTIONS };
