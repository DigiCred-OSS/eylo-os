import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type ScheduleRecord = components["schemas"]["ScheduleRead"];
type ScheduleRun = components["schemas"]["ScheduleRunRead"];
type ScheduleCreateInput = components["schemas"]["ScheduleCreate"];
type ScheduleUpdateInput = components["schemas"]["ScheduleUpdate"];
type ScheduleMisfirePolicy = components["schemas"]["MisfirePolicy"];
type ScheduleAgent = components["schemas"]["AgentResponseSchema"];
type ScheduleFilterProperty = "enabled" | "lifecycle" | "misfire_policy";
type ScheduleSortField = "name" | "next_at" | "last_fired_at" | "lifecycle";
type ScheduleSortDirection = "asc" | "desc";

interface ScheduleCollectionQuery {
  direction: ScheduleSortDirection;
  filters: FilterGroup<ScheduleFilterProperty>;
  search: string;
  sortBy: ScheduleSortField;
}

interface ScheduleFormValues {
  action: string;
  agentId: string;
  endsAt: string;
  key: string;
  misfirePolicy: ScheduleMisfirePolicy;
  name: string;
  payload: string;
  recurrence: "once" | "daily" | "weekdays" | "weekly" | "custom";
  rule: string;
  startsAt: string;
  timezone: string;
}

export type {
  ScheduleAgent,
  ScheduleCollectionQuery,
  ScheduleCreateInput,
  ScheduleFilterProperty,
  ScheduleFormValues,
  ScheduleMisfirePolicy,
  ScheduleRecord,
  ScheduleRun,
  ScheduleSortDirection,
  ScheduleSortField,
  ScheduleUpdateInput,
};
