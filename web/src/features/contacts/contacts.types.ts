import type { components, operations } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type Contact = components["schemas"]["ContactApiResponseSchema"];
type ContactsPage = components["schemas"]["ContactsPaginated"];
type ContactCreateInput = components["schemas"]["ContactCreateRequestSchema"];
type ContactUpdateInput = components["schemas"]["ContactPatchRequestSchema"];
type ContactLifecycle = components["schemas"]["ContactLifecycle"];
type ContactSortField = components["schemas"]["ContactSortField"];
type ContactSortDirection = components["schemas"]["ContactSortDirection"];
type DeletionJob = components["schemas"]["DeletionJobApiResponse"];
type ContactListApiQuery = NonNullable<
  operations["list_contacts_api__organization_id__contacts_get"]["parameters"]["query"]
>;
type ContactFilterProperty = "lifecycle";
type ContactFormMode = "create" | "edit";

interface ContactCollectionQuery {
  direction: ContactSortDirection;
  filters: FilterGroup<ContactFilterProperty>;
  limit: number;
  page: number;
  search: string;
  sortBy: ContactSortField;
}

interface ContactFormValues {
  externalId: string;
  name: string;
  preferences: Record<string, string>;
  primaryEmail: string;
  primaryPhone: string;
}

const CONTACTS_PAGE_SIZE = 20;
const CONTACT_LIFECYCLES = [
  "active",
  "deletion_pending",
] as const satisfies readonly ContactLifecycle[];
const CONTACT_SORT_FIELDS = [
  "name",
  "primary_email",
  "primary_phone",
  "created_at",
  "updated_at",
] as const satisfies readonly ContactSortField[];
const CONTACT_SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly ContactSortDirection[];

export {
  CONTACTS_PAGE_SIZE,
  CONTACT_LIFECYCLES,
  CONTACT_SORT_DIRECTIONS,
  CONTACT_SORT_FIELDS,
};
export type {
  Contact,
  ContactCollectionQuery,
  ContactCreateInput,
  ContactFilterProperty,
  ContactFormMode,
  ContactFormValues,
  ContactLifecycle,
  ContactListApiQuery,
  ContactsPage,
  ContactSortDirection,
  ContactSortField,
  ContactUpdateInput,
  DeletionJob,
};
