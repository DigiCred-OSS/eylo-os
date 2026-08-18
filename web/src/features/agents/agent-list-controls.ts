import { Bot, CalendarDays, CircleDot, Clock3, Type } from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import {
  AGENT_KINDS,
  AGENT_STATUSES,
  type Agent,
  type AgentFilterProperty,
  type AgentSortField,
} from "@/features/agents/agents.types";

const AGENT_FILTER_SCHEMA = [
  {
    accessor: (agent: Agent) => agent.status,
    icon: CircleDot,
    keywords: ["lifecycle", "state"],
    label: "Status",
    operators: ["is"],
    options: AGENT_STATUSES.map((status) => ({
      keywords: [status.toLocaleLowerCase()],
      label: formatAgentEnum(status),
      value: status,
    })),
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (agent: Agent) => agent.kind,
    icon: Bot,
    keywords: ["type", "runtime"],
    label: "Kind",
    operators: ["is"],
    options: AGENT_KINDS.map((kind) => ({
      keywords: [kind.toLocaleLowerCase()],
      label: formatAgentEnum(kind),
      value: kind,
    })),
    property: "kind",
    valueType: "multi-select",
  },
] as const satisfies FilterUiSchema<Agent, AgentFilterProperty>;

const AGENT_SORT_OPTIONS = [
  { icon: Type, label: "Name", value: "name" },
  { icon: CircleDot, label: "Status", value: "status" },
  { icon: Bot, label: "Kind", value: "kind" },
  { icon: CalendarDays, label: "Created", value: "created_at" },
  { icon: Clock3, label: "Updated", value: "updated_at" },
] as const satisfies readonly SortOption<AgentSortField>[];

export { AGENT_FILTER_SCHEMA, AGENT_SORT_OPTIONS };
