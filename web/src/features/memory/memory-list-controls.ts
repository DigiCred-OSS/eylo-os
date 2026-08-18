import {
  Bot,
  CalendarClock,
  CalendarPlus,
  CircleDot,
  Clock3,
  MessagesSquare,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  Memory,
  MemoryFilterProperty,
  MemorySortField,
} from "@/features/memory/memory.types";

const MEMORY_SORT_OPTIONS = [
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
  { icon: CalendarPlus, label: "Saved date", value: "created_at" },
  { icon: RefreshCcw, label: "Last recalled", value: "last_recalled_at" },
  { icon: Clock3, label: "Expiry date", value: "expires_at" },
  { icon: MessagesSquare, label: "Recall count", value: "recall_count" },
] as const satisfies readonly SortOption<MemorySortField>[];

const MEMORY_FILTER_SCHEMA: FilterUiSchema<Memory, MemoryFilterProperty> = [
  {
    accessor: (memory) => memory.integrity,
    icon: ShieldCheck,
    keywords: ["conflict", "duplicate", "reconciling", "quality"],
    label: "Integrity",
    operators: ["is"],
    options: [
      { label: "Checking", value: "checking" },
      { label: "Conflicted", value: "conflicted" },
      { label: "Consolidated", value: "consolidated" },
      { label: "Healthy", value: "healthy" },
    ],
    property: "integrity",
    valueType: "multi-select",
  },
  {
    accessor: (memory) => memory.level,
    icon: Bot,
    keywords: ["scope", "owner", "subject"],
    label: "Level",
    operators: ["is"],
    options: [
      { label: "Agent", value: "agent" },
      { label: "User", value: "user" },
      { label: "Conversation", value: "conversation" },
    ],
    property: "level",
    valueType: "multi-select",
  },
  {
    accessor: (memory) => memory.status,
    icon: CircleDot,
    keywords: ["active", "forgotten", "expired"],
    label: "Lifecycle",
    operators: ["is"],
    options: [
      { label: "Active", value: "active" },
      { label: "Expired", value: "expired" },
    ],
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (memory) => memory.recall_count > 0,
    icon: RefreshCcw,
    keywords: ["used", "retrieved", "never used"],
    label: "Recall",
    operators: ["is"],
    options: [
      { label: "Recalled", value: "recalled" },
      { label: "Not recalled", value: "not_recalled" },
    ],
    property: "recalled",
    valueType: "single-select",
  },
];

export { MEMORY_FILTER_SCHEMA, MEMORY_SORT_OPTIONS };
