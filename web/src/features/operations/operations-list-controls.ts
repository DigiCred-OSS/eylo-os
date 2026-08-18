import {
  Activity,
  CalendarClock,
  CircleGauge,
  GitBranch,
  MessageSquareText,
  Radio,
  Rows3,
  Target,
  Timer,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  AgentRun,
  AgentRunFilterProperty,
  AgentRunSortField,
  VoiceSession,
  VoiceSessionFilterProperty,
  VoiceSessionSortField,
} from "@/features/operations/operations.types";

const AGENT_RUN_SORT_OPTIONS = [
  { icon: CalendarClock, label: "Created date", value: "created_at" },
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
  { icon: Target, label: "Goal", value: "goal" },
  { icon: GitBranch, label: "Lifecycle", value: "lifecycle" },
] as const satisfies readonly SortOption<AgentRunSortField>[];

const AGENT_RUN_FILTER_SCHEMA: FilterUiSchema<
  AgentRun,
  AgentRunFilterProperty
> = [
  {
    accessor: (run) => run.lifecycle,
    icon: GitBranch,
    label: "Lifecycle",
    operators: ["is"],
    options: [
      "queued",
      "running",
      "waiting_for_input",
      "waiting_for_approval",
      "completed",
      "failed",
      "cancelled",
    ].map(option),
    property: "lifecycle",
    valueType: "multi-select",
  },
  {
    accessor: (run) => run.outcome,
    icon: Target,
    label: "Outcome",
    operators: ["is"],
    options: [
      "achieved",
      "unachievable",
      "failed",
      "cancelled",
      "exhausted",
    ].map(option),
    property: "outcome",
    valueType: "multi-select",
  },
  {
    accessor: (run) => run.origin_kind,
    icon: Activity,
    label: "Origin",
    operators: ["is"],
    options: ["message", "schedule_occurrence", "objective"].map(option),
    property: "origin",
    valueType: "multi-select",
  },
];

const VOICE_SESSION_SORT_OPTIONS = [
  { icon: CalendarClock, label: "Started date", value: "started_at" },
  { icon: Timer, label: "Duration", value: "duration" },
  { icon: CircleGauge, label: "Status", value: "status" },
  { icon: Rows3, label: "Segments", value: "segments" },
] as const satisfies readonly SortOption<VoiceSessionSortField>[];

const VOICE_SESSION_FILTER_SCHEMA: FilterUiSchema<
  VoiceSession,
  VoiceSessionFilterProperty
> = [
  {
    accessor: (session) => session.status,
    icon: CircleGauge,
    label: "Status",
    operators: ["is"],
    options: ["active", "completed", "failed"].map(option),
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (session) => session.runtimeMode,
    icon: Radio,
    label: "Runtime",
    operators: ["is"],
    options: ["browser_decomposed", "browser_realtime", "telephony"].map(
      option,
    ),
    property: "runtime",
    valueType: "multi-select",
  },
  {
    accessor: (session) => session.canonicalState,
    icon: MessageSquareText,
    label: "Transcript state",
    operators: ["is"],
    options: ["not_run", "clean", "redacted", "failed", "no_storage"].map(
      option,
    ),
    property: "canonical_state",
    valueType: "multi-select",
  },
];

function option(value: string): { label: string; value: string } {
  return {
    label: value
      .replaceAll("_", " ")
      .replace(/\b\w/g, (character) => character.toLocaleUpperCase()),
    value,
  };
}

export {
  AGENT_RUN_FILTER_SCHEMA,
  AGENT_RUN_SORT_OPTIONS,
  VOICE_SESSION_FILTER_SCHEMA,
  VOICE_SESSION_SORT_OPTIONS,
};
