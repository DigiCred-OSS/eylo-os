import {
  ArrowDownUp,
  CalendarClock,
  CircleGauge,
  Phone,
  Radio,
  Tag,
  Timer,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { formatTelephonyEnum } from "@/features/telephony/telephony-formatters";
import type {
  CallFilterProperty,
  CallSortField,
  PhoneNumber,
  PhoneNumberFilterProperty,
  PhoneNumberSortField,
  TelephonyCall,
} from "@/features/telephony/telephony.types";

const PROVIDERS = ["twilio", "plivo", "vonage", "exotel"] as const;
const PHONE_STATUSES = [
  "ACTIVE",
  "INACTIVE",
  "PROVISIONING",
  "PROVISIONING_UNKNOWN",
  "PROVISIONING_FAILED",
] as const;
const CALL_DIRECTIONS = ["inbound", "outbound"] as const;
const CALL_STATUSES = [
  "initiated",
  "ringing",
  "in-progress",
  "completed",
  "busy",
  "no-answer",
  "failed",
  "canceled",
] as const;

const PHONE_NUMBER_FILTER_SCHEMA: FilterUiSchema<
  PhoneNumber,
  PhoneNumberFilterProperty
> = [
  {
    accessor: (number) => number.status,
    icon: CircleGauge,
    label: "Status",
    operators: ["is"],
    options: PHONE_STATUSES.map(option),
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (number) => number.provider,
    icon: Radio,
    label: "Provider",
    operators: ["is"],
    options: PROVIDERS.map(option),
    property: "provider",
    valueType: "multi-select",
  },
];

const PHONE_NUMBER_SORT_OPTIONS = [
  { icon: Phone, label: "Phone number", value: "number" },
  { icon: Tag, label: "Label", value: "label" },
  { icon: CircleGauge, label: "Status", value: "status" },
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
] as const satisfies readonly SortOption<PhoneNumberSortField>[];

const CALL_FILTER_SCHEMA: FilterUiSchema<TelephonyCall, CallFilterProperty> = [
  {
    accessor: (call) => call.status,
    icon: CircleGauge,
    label: "Status",
    operators: ["is"],
    options: CALL_STATUSES.map(option),
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (call) => call.direction,
    icon: ArrowDownUp,
    label: "Direction",
    operators: ["is"],
    options: CALL_DIRECTIONS.map(option),
    property: "direction",
    valueType: "multi-select",
  },
  {
    accessor: (call) => call.provider,
    icon: Radio,
    label: "Provider",
    operators: ["is"],
    options: PROVIDERS.map(option),
    property: "provider",
    valueType: "multi-select",
  },
];

const CALL_SORT_OPTIONS = [
  { icon: CalendarClock, label: "Started date", value: "started_at" },
  { icon: Timer, label: "Duration", value: "duration" },
  { icon: CircleGauge, label: "Status", value: "status" },
  { icon: Radio, label: "Provider", value: "provider" },
] as const satisfies readonly SortOption<CallSortField>[];

function option(value: string): { label: string; value: string } {
  return { label: formatTelephonyEnum(value), value };
}

export {
  CALL_FILTER_SCHEMA,
  CALL_SORT_OPTIONS,
  CALL_DIRECTIONS,
  CALL_STATUSES,
  PHONE_NUMBER_FILTER_SCHEMA,
  PHONE_NUMBER_SORT_OPTIONS,
  PHONE_STATUSES,
  PROVIDERS,
};
