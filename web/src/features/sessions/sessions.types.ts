import type { components, operations } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type UserSession = components["schemas"]["UserSessionRead"];
type UserSessionPage = components["schemas"]["UserSessionPage"];
type UserSessionEntryChannel = components["schemas"]["UserSessionEntryChannel"];
type UserSessionState = components["schemas"]["UserSessionState"];
type UserSessionSortDirection =
  components["schemas"]["UserSessionSortDirection"];
type UserSessionSortField = components["schemas"]["UserSessionSortField"];
type SessionTimelineCategory = components["schemas"]["TimelineCategory"];
type SessionTimelineEvent =
  components["schemas"]["UserSessionTimelineEventRead"];
type SessionTimelinePage = components["schemas"]["UserSessionTimelinePage"];
type UserSessionListApiQuery = NonNullable<
  operations["list_user_sessions_api__organization_id__sessions_get"]["parameters"]["query"]
>;

type SessionFilterProperty = "channel" | "state";

interface SessionCollectionQuery {
  direction: UserSessionSortDirection;
  filters: FilterGroup<SessionFilterProperty>;
  limit: number;
  page: number;
  search: string;
  sortBy: UserSessionSortField;
}

interface SessionTimelineQuery {
  categories: SessionTimelineCategory[];
  includeTechnical: boolean;
}

const USER_SESSION_CHANNELS = [
  "widget",
  "telephony",
  "api",
] as const satisfies readonly UserSessionEntryChannel[];
const USER_SESSION_STATES = [
  "active",
  "disconnected",
  "ended",
  "failed",
] as const satisfies readonly UserSessionState[];
const USER_SESSION_SORT_FIELDS = [
  "started_at",
  "last_activity_at",
  "state",
  "contact",
] as const satisfies readonly UserSessionSortField[];
const USER_SESSION_SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly UserSessionSortDirection[];
const SESSION_TIMELINE_CATEGORIES = [
  "session",
  "conversation",
  "message",
  "agent",
  "tool",
  "file",
  "voice",
  "telephony",
  "technical",
] as const satisfies readonly SessionTimelineCategory[];
const SESSION_PAGE_SIZE = 20;
const SESSION_TIMELINE_PAGE_SIZE = 100;

export {
  SESSION_PAGE_SIZE,
  SESSION_TIMELINE_CATEGORIES,
  SESSION_TIMELINE_PAGE_SIZE,
  USER_SESSION_CHANNELS,
  USER_SESSION_SORT_DIRECTIONS,
  USER_SESSION_SORT_FIELDS,
  USER_SESSION_STATES,
};
export type {
  SessionCollectionQuery,
  SessionFilterProperty,
  SessionTimelineCategory,
  SessionTimelineEvent,
  SessionTimelinePage,
  SessionTimelineQuery,
  UserSession,
  UserSessionEntryChannel,
  UserSessionListApiQuery,
  UserSessionPage,
  UserSessionSortDirection,
  UserSessionSortField,
  UserSessionState,
};
