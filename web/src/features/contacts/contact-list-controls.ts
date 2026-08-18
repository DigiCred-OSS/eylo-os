import {
  CalendarClock,
  CalendarPlus,
  CircleDot,
  Mail,
  Phone,
  UserRound,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  Contact,
  ContactFilterProperty,
  ContactSortField,
} from "@/features/contacts/contacts.types";

const CONTACT_SORT_OPTIONS = [
  { icon: UserRound, label: "Name", value: "name" },
  { icon: Mail, label: "Email", value: "primary_email" },
  { icon: Phone, label: "Phone", value: "primary_phone" },
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
  { icon: CalendarPlus, label: "Created date", value: "created_at" },
] as const satisfies readonly SortOption<ContactSortField>[];

const CONTACT_FILTER_SCHEMA: FilterUiSchema<Contact, ContactFilterProperty> = [
  {
    accessor: (contact) => contact.lifecycle,
    icon: CircleDot,
    keywords: ["active", "deletion", "pending"],
    label: "Lifecycle",
    operators: ["is"],
    options: [
      { label: "Active", value: "active" },
      { label: "Deletion pending", value: "deletion_pending" },
    ],
    property: "lifecycle",
    valueType: "multi-select",
  },
];

export { CONTACT_FILTER_SCHEMA, CONTACT_SORT_OPTIONS };
