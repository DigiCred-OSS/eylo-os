import { makeAutoObservable, runInAction } from "mobx";

import {
  SessionsService,
  SessionsServiceError,
} from "@/features/sessions/sessions.service";
import type {
  SessionCollectionQuery,
  SessionTimelineEvent,
  SessionTimelineQuery,
  UserSession,
} from "@/features/sessions/sessions.types";

const COLLECTION_ERROR =
  "Sessions could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR =
  "This session could not be loaded. It may no longer exist.";
const TIMELINE_ERROR = "This session timeline could not be loaded.";

class SessionsStore {
  collectionErrorMessage: string | null = null;
  hasMore = false;
  isCollectionLoading = false;
  isLoadingMoreTimeline = false;
  isSelectedLoading = false;
  isTimelineLoading = false;
  items: UserSession[] = [];
  limit = 20;
  page = 1;
  selectedErrorMessage: string | null = null;
  selectedSession: UserSession | null = null;
  timeline: SessionTimelineEvent[] = [];
  timelineErrorMessage: string | null = null;
  timelineHasMore = false;
  timelinePage = 1;
  timelineTotal = 0;
  total = 0;

  private collectionRequest: AbortController | null = null;
  private contextKey: string | null = null;
  private readonly service: SessionsService;
  private selectedRequest: AbortController | null = null;
  private timelineQueryKey: string | null = null;
  private timelineRequest: AbortController | null = null;

  constructor(service: SessionsService) {
    this.service = service;
    makeAutoObservable<
      this,
      | "collectionRequest"
      | "contextKey"
      | "selectedRequest"
      | "service"
      | "timelineQueryKey"
      | "timelineRequest"
    >(
      this,
      {
        collectionRequest: false,
        contextKey: false,
        selectedRequest: false,
        service: false,
        timelineQueryKey: false,
        timelineRequest: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(
    organizationId: string,
    query: SessionCollectionQuery,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    this.items = [];

    try {
      const result = await this.service.list(
        organizationId,
        query,
        request.signal,
      );
      if (request.signal.aborted || this.collectionRequest !== request) {
        return;
      }
      runInAction(() => {
        this.items = result.items;
        this.limit = result.limit;
        this.page = result.page;
        this.total = result.total;
        this.hasMore = result.page * result.limit < result.total;
      });
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request) {
        runInAction(() => {
          this.collectionErrorMessage = errorMessage(error, COLLECTION_ERROR);
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
    userSessionId: string,
  ): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    const contextKey = `${organizationId}:${userSessionId}`;
    this.contextKey = contextKey;
    this.selectedRequest = request;
    this.isSelectedLoading = true;

    try {
      const userSession = await this.service.get(
        organizationId,
        userSessionId,
        request.signal,
      );
      if (request.signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.selectedSession = userSession;
      });
    } catch (error) {
      if (!request.signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.selectedErrorMessage = errorMessage(error, DETAIL_ERROR);
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

  async loadTimeline(
    organizationId: string,
    userSessionId: string,
    query: SessionTimelineQuery,
  ): Promise<void> {
    this.timelineRequest?.abort();
    const request = new AbortController();
    const contextKey = `${organizationId}:${userSessionId}`;
    const queryKey = JSON.stringify(query);
    this.timelineRequest = request;
    this.timelineQueryKey = queryKey;
    this.timelineErrorMessage = null;
    this.isLoadingMoreTimeline = false;
    this.isTimelineLoading = true;
    this.timeline = [];
    this.timelineHasMore = false;
    this.timelinePage = 1;
    this.timelineTotal = 0;

    try {
      const result = await this.service.timeline(
        organizationId,
        userSessionId,
        query,
        1,
        request.signal,
      );
      if (
        request.signal.aborted ||
        this.contextKey !== contextKey ||
        this.timelineQueryKey !== queryKey
      ) {
        return;
      }
      runInAction(() => {
        this.timeline = result.items;
        this.timelinePage = result.page;
        this.timelineTotal = result.total;
        this.timelineHasMore = result.page * result.limit < result.total;
      });
    } catch (error) {
      if (
        !request.signal.aborted &&
        this.contextKey === contextKey &&
        this.timelineQueryKey === queryKey
      ) {
        runInAction(() => {
          this.timelineErrorMessage = errorMessage(error, TIMELINE_ERROR);
          this.timelineHasMore = false;
        });
      }
    } finally {
      if (this.timelineRequest === request) {
        runInAction(() => {
          this.timelineRequest = null;
          this.isTimelineLoading = false;
        });
      }
    }
  }

  async loadMoreTimeline(
    organizationId: string,
    userSessionId: string,
    query: SessionTimelineQuery,
  ): Promise<void> {
    if (
      this.isTimelineLoading ||
      this.isLoadingMoreTimeline ||
      !this.timelineHasMore
    ) {
      return;
    }
    this.timelineRequest?.abort();
    const request = new AbortController();
    const contextKey = `${organizationId}:${userSessionId}`;
    const queryKey = JSON.stringify(query);
    const nextPage = this.timelinePage + 1;
    this.timelineRequest = request;
    this.isLoadingMoreTimeline = true;
    this.timelineErrorMessage = null;

    try {
      const result = await this.service.timeline(
        organizationId,
        userSessionId,
        query,
        nextPage,
        request.signal,
      );
      if (
        request.signal.aborted ||
        this.contextKey !== contextKey ||
        this.timelineQueryKey !== queryKey
      ) {
        return;
      }
      runInAction(() => {
        const existing = new Set(this.timeline.map((event) => event.id));
        this.timeline = [
          ...this.timeline,
          ...result.items.filter((event) => !existing.has(event.id)),
        ];
        this.timelinePage = result.page;
        this.timelineTotal = result.total;
        this.timelineHasMore = result.page * result.limit < result.total;
      });
    } catch (error) {
      if (
        !request.signal.aborted &&
        this.contextKey === contextKey &&
        this.timelineQueryKey === queryKey
      ) {
        runInAction(() => {
          this.timelineErrorMessage = errorMessage(error, TIMELINE_ERROR);
        });
      }
    } finally {
      if (this.timelineRequest === request) {
        runInAction(() => {
          this.timelineRequest = null;
          this.isLoadingMoreTimeline = false;
        });
      }
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.timelineRequest?.abort();
    this.selectedRequest = null;
    this.timelineRequest = null;
    this.contextKey = null;
    this.timelineQueryKey = null;
    this.selectedSession = null;
    this.selectedErrorMessage = null;
    this.timeline = [];
    this.timelineErrorMessage = null;
    this.timelineHasMore = false;
    this.timelinePage = 1;
    this.timelineTotal = 0;
    this.isSelectedLoading = false;
    this.isTimelineLoading = false;
    this.isLoadingMoreTimeline = false;
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof SessionsServiceError ? error.message : fallback;
}

export { SessionsStore };
