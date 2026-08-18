import type { components, operations } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type Member = components["schemas"]["MemberApiResponseSchema"];
type MembersPage = components["schemas"]["MembersPaginated"];
type MemberStatus = components["schemas"]["MemberStatus"];
type MemberSortField = components["schemas"]["MemberSortField"];
type MemberSortDirection = components["schemas"]["MemberSortDirection"];
type MemberListApiQuery = NonNullable<
  operations["list_members_api__organization_id__members_get"]["parameters"]["query"]
>;
type MemberFilterProperty = "status";

interface MemberCollectionQuery {
  direction: MemberSortDirection;
  filters: FilterGroup<MemberFilterProperty>;
  limit: number;
  page: number;
  search: string;
  sortBy: MemberSortField;
}

const MEMBERS_PAGE_SIZE = 20;
const MEMBER_STATUSES = [
  "ACTIVE",
  "INACTIVE",
  "WAITLIST",
] as const satisfies readonly MemberStatus[];
const MEMBER_SORT_FIELDS = [
  "name",
  "email",
  "status",
  "last_login",
  "created_at",
] as const satisfies readonly MemberSortField[];
const MEMBER_SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly MemberSortDirection[];

export {
  MEMBERS_PAGE_SIZE,
  MEMBER_SORT_DIRECTIONS,
  MEMBER_SORT_FIELDS,
  MEMBER_STATUSES,
};
export type {
  Member,
  MemberCollectionQuery,
  MemberFilterProperty,
  MemberListApiQuery,
  MembersPage,
  MemberSortDirection,
  MemberSortField,
  MemberStatus,
};
