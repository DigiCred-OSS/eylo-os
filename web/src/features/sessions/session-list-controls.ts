import { CalendarDays, CircleDot, Clock3, Radio, Type } from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { formatSessionEnum } from "@/features/sessions/session-formatters";
import {
  USER_SESSION_CHANNELS,
  USER_SESSION_STATES,
  type SessionFilterProperty,
  type UserSession,
  type UserSessionSortField,
} from "@/features/sessions/sessions.types";

const SESSION_FILTER_SCHEMA = [
  {
    accessor: (item: UserSession) => item.state,
    icon: CircleDot,
    keywords: ["lifecycle", "status"],
    label: "State",
    operators: ["is"],
    options: USER_SESSION_STATES.map((state) => ({
      keywords: [state],
      label: formatSessionEnum(state),
      value: state,
    })),
    property: "state",
    valueType: "multi-select",
  },
  {
    accessor: (item: UserSession) => item.entryChannel,
    icon: Radio,
    keywords: ["entry", "source", "transport"],
    label: "Entry channel",
    operators: ["is"],
    options: USER_SESSION_CHANNELS.map((channel) => ({
      keywords: [channel],
      label: formatSessionEnum(channel),
      value: channel,
    })),
    property: "channel",
    valueType: "multi-select",
  },
] as const satisfies FilterUiSchema<UserSession, SessionFilterProperty>;

const SESSION_SORT_OPTIONS = [
  { icon: CalendarDays, label: "Started", value: "started_at" },
  { icon: Clock3, label: "Last activity", value: "last_activity_at" },
  { icon: CircleDot, label: "State", value: "state" },
  { icon: Type, label: "Contact", value: "contact" },
] as const satisfies readonly SortOption<UserSessionSortField>[];

export { SESSION_FILTER_SCHEMA, SESSION_SORT_OPTIONS };
