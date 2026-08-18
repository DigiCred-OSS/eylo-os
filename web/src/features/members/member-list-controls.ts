import { CalendarPlus, CircleDot, Mail, UserRound } from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  Member,
  MemberFilterProperty,
  MemberSortField,
} from "@/features/members/members.types";

const MEMBER_SORT_OPTIONS = [
  { icon: UserRound, label: "Name", value: "name" },
  { icon: Mail, label: "Email", value: "email" },
  { icon: CircleDot, label: "Status", value: "status" },
  { icon: CalendarPlus, label: "Last login", value: "last_login" },
  { icon: CalendarPlus, label: "Joined date", value: "created_at" },
] as const satisfies readonly SortOption<MemberSortField>[];

const MEMBER_FILTER_SCHEMA: FilterUiSchema<Member, MemberFilterProperty> = [
  {
    accessor: (member) => member.status,
    icon: CircleDot,
    keywords: ["active", "inactive", "waitlist"],
    label: "Status",
    operators: ["is"],
    options: [
      { label: "Active", value: "ACTIVE" },
      { label: "Inactive", value: "INACTIVE" },
      { label: "Waitlist", value: "WAITLIST" },
    ],
    property: "status",
    valueType: "multi-select",
  },
];

export { MEMBER_FILTER_SCHEMA, MEMBER_SORT_OPTIONS };
