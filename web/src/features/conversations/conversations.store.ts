import { makeAutoObservable, runInAction } from "mobx";

import {
  ConversationsService,
  ConversationsServiceError,
} from "@/features/conversations/conversations.service";
import type {
  ConversationAggregate,
  ConversationCollectionQuery,
  ConversationListItem,
  ConversationMessage,
  ConversationParticipant,
  ConversationRecording,
  ConversationRecordingAudioState,
  ConversationRecordingTrack,
  ConversationVoiceSession,
} from "@/features/conversations/conversations.types";

const COLLECTION_ERROR =
  "Conversations could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR =
  "This conversation could not be loaded. It may no longer exist.";
const IDLE_RECORDING_AUDIO: ConversationRecordingAudioState = {
  errorMessage: null,
  objectUrl: null,
  status: "idle",
};

class ConversationsStore {
  collectionErrorMessage: string | null = null;
  hasMore = false;
  isCollectionLoading = false;
  isLoadingMoreMessages = false;
  isSelectedLoading = false;
  items: ConversationListItem[] = [];
  limit = 20;
  messages: ConversationMessage[] = [];
  messagesErrorMessage: string | null = null;
  messagesHasMore = false;
  messagesPage = 1;
  messagesTotal = 0;
  page = 1;
  participants: ConversationParticipant[] = [];
  participantsErrorMessage: string | null = null;
  recordings: ConversationRecording[] = [];
  recordingAudio = new Map<string, ConversationRecordingAudioState>();
  recordingsErrorMessage: string | null = null;
  voiceSession: ConversationVoiceSession | null = null;
  voiceSessionErrorMessage: string | null = null;
  selectedConversation: ConversationAggregate | null = null;
  selectedErrorMessage: string | null = null;
  total = 0;

  private collectionRequest: AbortController | null = null;
  private contextKey: string | null = null;
  private messageRequest: AbortController | null = null;
  private recordingAudioRequests = new Map<string, AbortController>();
  private selectedRequest: AbortController | null = null;
  private readonly service: ConversationsService;

  constructor(service: ConversationsService) {
    this.service = service;
    makeAutoObservable<
      this,
      | "collectionRequest"
      | "contextKey"
      | "messageRequest"
      | "recordingAudioRequests"
      | "selectedRequest"
      | "service"
    >(
      this,
      {
        collectionRequest: false,
        contextKey: false,
        messageRequest: false,
        recordingAudioRequests: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(
    organizationId: string,
    query: ConversationCollectionQuery,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    const contextKey = `${organizationId}:${JSON.stringify(query)}`;
    this.collectionRequest = request;
    this.contextKey = contextKey;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    this.items = [];

    try {
      const page = await this.service.listConversations(
        organizationId,
        query,
        request.signal,
      );
      if (request.signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.hasMore = page.hasMore;
        this.items = page.items;
        this.limit = page.limit;
        this.page = page.page;
        this.total = page.total;
      });
    } catch (error) {
      if (!request.signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.collectionErrorMessage = message(error, COLLECTION_ERROR);
          this.hasMore = false;
          this.total = 0;
        });
      }
    } finally {
      if (this.collectionRequest === request) {
        runInAction(() => {
          this.collectionRequest = null;
          this.isCollectionLoading = false;
        });
      }
    }
  }

  async loadSelected(
    organizationId: string,
    conversationId: string,
  ): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    const contextKey = `${organizationId}:${conversationId}`;
    this.contextKey = contextKey;
    this.selectedRequest = request;
    this.isSelectedLoading = true;

    try {
      const conversation = await this.service.getConversation(
        organizationId,
        conversationId,
        request.signal,
      );
      if (request.signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.selectedConversation = conversation;
      });
      await this.loadRelations(
        organizationId,
        conversationId,
        contextKey,
        request.signal,
      );
    } catch (error) {
      if (!request.signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.selectedErrorMessage = message(error, DETAIL_ERROR);
        });
      }
    } finally {
      if (this.selectedRequest === request) {
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
      }
    }
  }

  async loadMoreMessages(
    organizationId: string,
    conversationId: string,
  ): Promise<void> {
    if (this.isLoadingMoreMessages || !this.messagesHasMore) {
      return;
    }
    this.messageRequest?.abort();
    const request = new AbortController();
    const contextKey = `${organizationId}:${conversationId}`;
    const nextPage = this.messagesPage + 1;
    this.messageRequest = request;
    this.isLoadingMoreMessages = true;
    this.messagesErrorMessage = null;
    try {
      const page = await this.service.listMessages(
        organizationId,
        conversationId,
        nextPage,
        request.signal,
      );
      if (request.signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        const existing = new Set(this.messages.map((item) => item.id));
        this.messages = [
          ...this.messages,
          ...page.data.filter((item) => !existing.has(item.id)),
        ];
        this.messagesHasMore = Boolean(page.hasMore);
        this.messagesPage = page.page;
        this.messagesTotal = page.total ?? this.messages.length;
      });
    } catch (error) {
      if (!request.signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.messagesErrorMessage = message(
            error,
            "More transcript messages could not be loaded.",
          );
        });
      }
    } finally {
      if (this.messageRequest === request) {
        runInAction(() => {
          this.messageRequest = null;
          this.isLoadingMoreMessages = false;
        });
      }
    }
  }

  recordingAudioFor(
    recordingId: string,
    track: ConversationRecordingTrack,
  ): ConversationRecordingAudioState {
    return (
      this.recordingAudio.get(recordingAudioKey(recordingId, track)) ??
      IDLE_RECORDING_AUDIO
    );
  }

  async loadRecordingTrack(
    organizationId: string,
    conversationId: string,
    recordingId: string,
    track: ConversationRecordingTrack,
  ): Promise<void> {
    const key = recordingAudioKey(recordingId, track);
    const current = this.recordingAudio.get(key);
    if (current?.status === "ready" || current?.status === "loading") {
      return;
    }

    const request = new AbortController();
    const contextKey = `${organizationId}:${conversationId}`;
    this.recordingAudioRequests.set(key, request);
    this.recordingAudio.set(key, {
      errorMessage: null,
      objectUrl: null,
      status: "loading",
    });

    try {
      const blob = await this.service.downloadRecordingTrack(
        organizationId,
        conversationId,
        recordingId,
        track,
        request.signal,
      );
      if (request.signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      const objectUrl = URL.createObjectURL(blob);
      runInAction(() => {
        this.recordingAudio.set(key, {
          errorMessage: null,
          objectUrl,
          status: "ready",
        });
      });
    } catch (error) {
      if (!request.signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.recordingAudio.set(key, {
            errorMessage: message(
              error,
              "This recording track could not be loaded.",
            ),
            objectUrl: null,
            status: "error",
          });
        });
      }
    } finally {
      if (this.recordingAudioRequests.get(key) === request) {
        this.recordingAudioRequests.delete(key);
      }
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.messageRequest?.abort();
    this.selectedRequest = null;
    this.messageRequest = null;
    this.clearRecordingAudio();
    this.contextKey = null;
    this.selectedConversation = null;
    this.selectedErrorMessage = null;
    this.messages = [];
    this.messagesErrorMessage = null;
    this.messagesHasMore = false;
    this.messagesPage = 1;
    this.messagesTotal = 0;
    this.participants = [];
    this.participantsErrorMessage = null;
    this.recordings = [];
    this.recordingsErrorMessage = null;
    this.voiceSession = null;
    this.voiceSessionErrorMessage = null;
    this.isSelectedLoading = false;
    this.isLoadingMoreMessages = false;
  }

  private clearRecordingAudio(): void {
    for (const request of this.recordingAudioRequests.values()) {
      request.abort();
    }
    this.recordingAudioRequests.clear();
    for (const state of this.recordingAudio.values()) {
      if (state.objectUrl !== null) {
        URL.revokeObjectURL(state.objectUrl);
      }
    }
    this.recordingAudio.clear();
  }

  private async loadRelations(
    organizationId: string,
    conversationId: string,
    contextKey: string,
    signal: AbortSignal,
  ): Promise<void> {
    await Promise.allSettled([
      this.loadInitialMessages(
        organizationId,
        conversationId,
        contextKey,
        signal,
      ),
      this.loadParticipants(organizationId, conversationId, contextKey, signal),
      this.loadRecordings(organizationId, conversationId, contextKey, signal),
      this.loadVoiceSession(organizationId, conversationId, contextKey, signal),
    ]);
  }

  private async loadInitialMessages(
    organizationId: string,
    conversationId: string,
    contextKey: string,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      const page = await this.service.listMessages(
        organizationId,
        conversationId,
        1,
        signal,
      );
      if (signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.messages = page.data;
        this.messagesHasMore = Boolean(page.hasMore);
        this.messagesPage = page.page;
        this.messagesTotal = page.total ?? page.data.length;
      });
    } catch (error) {
      if (!signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.messagesErrorMessage = message(
            error,
            "The transcript could not be loaded.",
          );
        });
      }
    }
  }

  private async loadParticipants(
    organizationId: string,
    conversationId: string,
    contextKey: string,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      const participants = await this.service.listAllParticipants(
        organizationId,
        conversationId,
        signal,
      );
      if (signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.participants = participants;
      });
    } catch (error) {
      if (!signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.participantsErrorMessage = message(
            error,
            "Conversation participants could not be loaded.",
          );
        });
      }
    }
  }

  private async loadRecordings(
    organizationId: string,
    conversationId: string,
    contextKey: string,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      const recordings = await this.service.listRecordings(
        organizationId,
        conversationId,
        signal,
      );
      if (signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.recordings = recordings;
      });
    } catch (error) {
      if (!signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.recordingsErrorMessage = message(
            error,
            "Voice recordings could not be loaded.",
          );
        });
      }
    }
  }

  private async loadVoiceSession(
    organizationId: string,
    conversationId: string,
    contextKey: string,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      const voiceSession = await this.service.getVoiceSession(
        organizationId,
        conversationId,
        signal,
      );
      if (signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.voiceSession = voiceSession;
      });
    } catch (error) {
      if (!signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.voiceSessionErrorMessage = message(
            error,
            "Voice session details could not be loaded.",
          );
        });
      }
    }
  }
}

function recordingAudioKey(
  recordingId: string,
  track: ConversationRecordingTrack,
): string {
  return `${recordingId}:${track}`;
}

function message(error: unknown, fallback: string): string {
  return error instanceof ConversationsServiceError ? error.message : fallback;
}

export { ConversationsStore };
