import type { ApiClient } from "@/api/client";
import { toConversationListApiQuery } from "@/features/conversations/conversations.query";
import {
  CONVERSATION_MESSAGES_PAGE_SIZE,
  type ConversationAggregate,
  type ConversationCollectionQuery,
  type ConversationListPage,
  type ConversationMessagesPage,
  type ConversationParticipant,
  type ConversationParticipantsPage,
  type ConversationRecording,
  type ConversationRecordingTrack,
  type ConversationVoiceSession,
  type ConversationsPage,
} from "@/features/conversations/conversations.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class ConversationsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ConversationsServiceError";
    this.status = status;
  }
}

class ConversationsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listConversations(
    organizationId: string,
    query: ConversationCollectionQuery,
    signal?: AbortSignal,
  ): Promise<ConversationListPage> {
    const page = requireData<ConversationsPage>(
      await this.api.GET("/api/{organization_id}/conversations", {
        params: {
          path: { organization_id: organizationId },
          query: toConversationListApiQuery(query),
        },
        signal,
      }),
      "Conversations could not be loaded.",
    );
    const ids = page.data.map((conversation) => conversation.id);
    const aggregates =
      ids.length === 0
        ? []
        : requireData(
            await this.api.POST(
              "/api/{organization_id}/aggregate/conversations",
              {
                body: {
                  conversationIds: ids,
                  includeMessages: false,
                  includeParticipants: true,
                  messageLimit: 50,
                },
                params: { path: { organization_id: organizationId } },
                signal,
              },
            ),
            "Conversation context could not be loaded.",
          ).conversations;
    const aggregateById = new Map(
      aggregates.map((aggregate) => [aggregate.id, aggregate]),
    );
    const total = page.total ?? page.data.length;
    return {
      hasMore:
        page.hasMore ??
        page.page * page.limit < Math.max(total, page.data.length),
      items: page.data.map((conversation) => ({
        aggregate: aggregateById.get(conversation.id) ?? null,
        conversation,
      })),
      limit: page.limit,
      page: page.page,
      total,
    };
  }

  async getConversation(
    organizationId: string,
    conversationId: string,
    signal?: AbortSignal,
  ): Promise<ConversationAggregate> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/aggregate/conversations/{conversation_id}",
        {
          params: {
            path: {
              conversation_id: conversationId,
              organization_id: organizationId,
            },
            query: {
              include_messages: false,
              include_participants: true,
              message_limit: 50,
            },
          },
          signal,
        },
      ),
      "This conversation could not be loaded.",
    );
  }

  async listMessages(
    organizationId: string,
    conversationId: string,
    page: number,
    signal?: AbortSignal,
  ): Promise<ConversationMessagesPage> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/conversations/{conversation_id}/messages",
        {
          params: {
            path: {
              conversation_id: conversationId,
              organization_id: organizationId,
            },
            query: { limit: CONVERSATION_MESSAGES_PAGE_SIZE, page },
          },
          signal,
        },
      ),
      "The transcript could not be loaded.",
    );
  }

  async listAllParticipants(
    organizationId: string,
    conversationId: string,
    signal?: AbortSignal,
  ): Promise<ConversationParticipant[]> {
    const participants: ConversationParticipant[] = [];
    let pageNumber = 1;
    while (true) {
      const page = await this.listParticipantsPage(
        organizationId,
        conversationId,
        pageNumber,
        signal,
      );
      participants.push(...page.data);
      if (
        !page.hasMore ||
        page.data.length === 0 ||
        (page.total != null && participants.length >= page.total)
      ) {
        return participants;
      }
      pageNumber += 1;
    }
  }

  async listRecordings(
    organizationId: string,
    conversationId: string,
    signal?: AbortSignal,
  ): Promise<ConversationRecording[]> {
    const response = requireData(
      await this.api.GET(
        "/api/organizations/{organization_id}/conversations/{conversation_id}/recordings",
        {
          params: {
            path: {
              conversation_id: conversationId,
              organization_id: organizationId,
            },
          },
          signal,
        },
      ),
      "Voice recordings could not be loaded.",
    );
    return response.recordings;
  }

  async getVoiceSession(
    organizationId: string,
    conversationId: string,
    signal?: AbortSignal,
  ): Promise<ConversationVoiceSession | null> {
    const result = await this.api.GET(
      "/api/{organization_id}/conversations/{conversation_id}/voice-session",
      {
        params: {
          path: {
            conversation_id: conversationId,
            organization_id: organizationId,
          },
          query: { segment_limit: 1, segment_page: 1 },
        },
        signal,
      },
    );
    if (result.response.status === 404) {
      return null;
    }
    return requireData(result, "Voice session details could not be loaded.");
  }

  async downloadRecordingTrack(
    organizationId: string,
    conversationId: string,
    recordingId: string,
    track: ConversationRecordingTrack,
    signal?: AbortSignal,
  ): Promise<Blob> {
    const result = await this.api.GET(
      "/api/organizations/{organization_id}/conversations/{conversation_id}/recordings/{recording_id}/{track}",
      {
        params: {
          path: {
            conversation_id: conversationId,
            organization_id: organizationId,
            recording_id: recordingId,
            track,
          },
        },
        parseAs: "blob",
        signal,
      },
    );
    if (result.data instanceof Blob) {
      return result.data;
    }
    throw new ConversationsServiceError(
      "This recording track could not be loaded.",
      result.response.status,
    );
  }

  private async listParticipantsPage(
    organizationId: string,
    conversationId: string,
    page: number,
    signal?: AbortSignal,
  ): Promise<ConversationParticipantsPage> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/conversations/{conversation_id}/participants",
        {
          params: {
            path: {
              conversation_id: conversationId,
              organization_id: organizationId,
            },
            query: { limit: 100, page },
          },
          signal,
        },
      ),
      "Conversation participants could not be loaded.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) {
    return result.data;
  }
  throw new ConversationsServiceError(
    readDetail(result.error) ?? fallback,
    result.response.status,
  );
}

function readDetail(error: unknown): string | null {
  if (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    typeof error.detail === "string"
  ) {
    return error.detail;
  }
  return null;
}

export { ConversationsService, ConversationsServiceError };
