import type { components, operations } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type Conversation = components["schemas"]["ConversationApiResponseSchema"];
type ConversationAggregate =
  components["schemas"]["ConversationAggregateResponse"];
type ConversationChannel = components["schemas"]["ConversationChannels"];
type ConversationMessage = components["schemas"]["MessageApiResponseSchema"];
type ConversationParticipant =
  components["schemas"]["ParticipantApiResponseSchema"];
type ConversationRecording = components["schemas"]["VoiceRecordingResponse"];
type ConversationRecordingTrack = "user" | "agent";
type ConversationVoiceSession = components["schemas"]["VoiceSessionDetail"];
type ConversationSortDirection =
  components["schemas"]["ConversationSortDirection"];
type ConversationSortField = components["schemas"]["ConversationSort"];
type ConversationStatus = components["schemas"]["ConversationStatus"];
type ConversationsPage = components["schemas"]["ConversationsPaginated"];
type ConversationMessagesPage =
  components["schemas"]["ConversationMessagesPaginated"];
type ConversationParticipantsPage =
  components["schemas"]["ConversationParticipantsPaginated"];
type ConversationListApiQuery = NonNullable<
  operations["list_conversations_api__organization_id__conversations_get"]["parameters"]["query"]
>;

type ConversationFilterProperty = "channel" | "status";

interface ConversationCollectionQuery {
  direction: ConversationSortDirection;
  filters: FilterGroup<ConversationFilterProperty>;
  limit: number;
  page: number;
  search: string;
  sortBy: ConversationSortField;
}

interface ConversationListItem {
  aggregate: ConversationAggregate | null;
  conversation: Conversation;
}

interface ConversationListPage {
  hasMore: boolean;
  items: ConversationListItem[];
  limit: number;
  page: number;
  total: number;
}

interface ConversationRecordingAudioState {
  errorMessage: string | null;
  objectUrl: string | null;
  status: "idle" | "loading" | "ready" | "error";
}

const CONVERSATION_CHANNELS = [
  "PHONE",
  "CHAT",
  "WEB",
  "WIDGET",
  "SMS",
  "API",
] as const satisfies readonly ConversationChannel[];
const CONVERSATION_STATUSES = [
  "ACTIVE",
  "COMPLETED",
  "ABANDONED",
] as const satisfies readonly ConversationStatus[];
const CONVERSATION_SORT_FIELDS = [
  "updated_at",
  "created_at",
  "ended_at",
  "title",
] as const satisfies readonly ConversationSortField[];
const CONVERSATION_SORT_DIRECTIONS = [
  "asc",
  "desc",
] as const satisfies readonly ConversationSortDirection[];
const CONVERSATIONS_PAGE_SIZE = 20;
const CONVERSATION_MESSAGES_PAGE_SIZE = 100;

export {
  CONVERSATION_CHANNELS,
  CONVERSATION_MESSAGES_PAGE_SIZE,
  CONVERSATION_SORT_DIRECTIONS,
  CONVERSATION_SORT_FIELDS,
  CONVERSATION_STATUSES,
  CONVERSATIONS_PAGE_SIZE,
};
export type {
  Conversation,
  ConversationAggregate,
  ConversationChannel,
  ConversationCollectionQuery,
  ConversationFilterProperty,
  ConversationListApiQuery,
  ConversationListItem,
  ConversationListPage,
  ConversationMessage,
  ConversationMessagesPage,
  ConversationParticipant,
  ConversationParticipantsPage,
  ConversationRecording,
  ConversationRecordingAudioState,
  ConversationRecordingTrack,
  ConversationVoiceSession,
  ConversationsPage,
  ConversationSortDirection,
  ConversationSortField,
  ConversationStatus,
};
