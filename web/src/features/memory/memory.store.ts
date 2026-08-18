import { makeAutoObservable, runInAction } from "mobx";

import {
  MemoryService,
  MemoryServiceError,
} from "@/features/memory/memory.service";
import type {
  Memory,
  MemoryDetail,
  MemoryListRequest,
  MemoryReindexStatus,
} from "@/features/memory/memory.types";

const COLLECTION_ERROR =
  "Memories could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR = "This memory could not be loaded. It may no longer exist.";
const REINDEX_POLL_INTERVAL_MS = 2_000;

class MemoryStore {
  collectionErrorMessage: string | null = null;
  hasLoadedCollection = false;
  isCollectionLoading = false;
  isLoadingMore = false;
  isReindexStatusLoading = false;
  isReindexing = false;
  isSelectedLoading = false;
  items: Memory[] = [];
  reindexConfigId: string | null = null;
  reindexErrorMessage: string | null = null;
  reindexStatus: MemoryReindexStatus | null = null;
  selectedErrorMessage: string | null = null;
  selectedMemory: MemoryDetail | null = null;
  total = 0;

  private collectionRequest: AbortController | null = null;
  private contextKey: string | null = null;
  private lastRequest: MemoryListRequest | null = null;
  private reindexRequest: AbortController | null = null;
  private reindexTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly service: MemoryService;
  private selectedRequest: AbortController | null = null;

  constructor(service: MemoryService) {
    this.service = service;
    makeAutoObservable<
      this,
      | "collectionRequest"
      | "contextKey"
      | "lastRequest"
      | "reindexRequest"
      | "reindexTimer"
      | "selectedRequest"
      | "service"
    >(
      this,
      {
        collectionRequest: false,
        contextKey: false,
        lastRequest: false,
        reindexRequest: false,
        reindexTimer: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get canLoadMore(): boolean {
    return this.items.length < this.total;
  }

  get isCollectionStale(): boolean {
    return this.collectionErrorMessage !== null && this.items.length > 0;
  }

  async loadCollection(
    organizationId: string,
    request: MemoryListRequest,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const controller = new AbortController();
    const contextKey = buildContextKey(organizationId, request);
    this.collectionRequest = controller;
    this.contextKey = contextKey;
    this.lastRequest = { ...request, offset: 0 };
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    this.items = [];
    this.total = 0;

    try {
      const page = await this.service.listMemories(
        organizationId,
        { ...request, offset: 0 },
        controller.signal,
      );
      if (controller.signal.aborted || this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.items = page.items;
        this.total = page.total;
        this.hasLoadedCollection = true;
      });
    } catch (error) {
      if (!controller.signal.aborted && this.contextKey === contextKey) {
        runInAction(() => {
          this.collectionErrorMessage = message(error, COLLECTION_ERROR);
          this.hasLoadedCollection = true;
        });
      }
    } finally {
      if (this.collectionRequest === controller) {
        runInAction(() => {
          this.collectionRequest = null;
          this.isCollectionLoading = false;
        });
      }
    }
  }

  async loadMore(organizationId: string): Promise<void> {
    if (this.isLoadingMore || !this.canLoadMore || this.lastRequest === null) {
      return;
    }
    const request = { ...this.lastRequest, offset: this.items.length };
    const expectedKey = buildContextKey(organizationId, request);
    if (this.contextKey !== expectedKey) {
      return;
    }
    this.isLoadingMore = true;
    this.collectionErrorMessage = null;
    try {
      const page = await this.service.listMemories(organizationId, request);
      if (this.contextKey !== expectedKey) {
        return;
      }
      runInAction(() => {
        const existingIds = new Set(this.items.map((item) => item.id));
        this.items = [
          ...this.items,
          ...page.items.filter((item) => !existingIds.has(item.id)),
        ];
        this.total = page.total;
      });
    } catch (error) {
      if (this.contextKey === expectedKey) {
        runInAction(() => {
          this.collectionErrorMessage = message(error, COLLECTION_ERROR);
        });
      }
    } finally {
      runInAction(() => {
        this.isLoadingMore = false;
      });
    }
  }

  async loadSelected(organizationId: string, memoryId: string): Promise<void> {
    this.selectedRequest?.abort();
    const controller = new AbortController();
    this.selectedRequest = controller;
    this.selectedMemory = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;
    try {
      const memory = await this.service.getMemory(
        organizationId,
        memoryId,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        runInAction(() => {
          this.selectedMemory = memory;
          this.items = this.items.map((item) =>
            item.id === memory.id ? memory : item,
          );
        });
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        runInAction(() => {
          this.selectedErrorMessage = message(error, DETAIL_ERROR);
        });
      }
    } finally {
      if (this.selectedRequest === controller) {
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
      }
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedMemory = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
  }

  async loadReindexStatus(configId: string): Promise<void> {
    this.clearReindexTimer();
    this.reindexRequest?.abort();
    const request = new AbortController();
    this.reindexConfigId = configId;
    this.reindexRequest = request;
    this.isReindexStatusLoading = true;
    this.reindexStatus = null;
    this.reindexErrorMessage = null;

    try {
      const status = await this.service.getReindexStatus(
        configId,
        request.signal,
      );
      if (request.signal.aborted || this.reindexConfigId !== configId) {
        return;
      }
      runInAction(() => {
        this.reindexStatus = status;
        this.reindexErrorMessage = null;
      });
      if (shouldPoll(status)) {
        this.scheduleReindexStatusRefresh(configId);
      }
    } catch (error) {
      if (!request.signal.aborted && this.reindexConfigId === configId) {
        runInAction(() => {
          this.reindexErrorMessage = message(
            error,
            "Memory index status could not be loaded.",
          );
        });
      }
    } finally {
      if (this.reindexRequest === request) {
        runInAction(() => {
          this.reindexRequest = null;
          this.isReindexStatusLoading = false;
        });
      }
    }
  }

  async startReindex(configId: string): Promise<boolean> {
    if (this.isReindexing) {
      return false;
    }
    this.isReindexing = true;
    this.reindexErrorMessage = null;
    try {
      await this.service.reindex(configId);
      if (this.reindexConfigId !== configId) {
        return true;
      }
      await this.loadReindexStatus(configId);
      return true;
    } catch (error) {
      if (this.reindexConfigId === configId) {
        runInAction(() => {
          this.reindexErrorMessage = message(
            error,
            "Memory reindex could not be started.",
          );
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.isReindexing = false;
      });
    }
  }

  clearReindexStatus(): void {
    this.clearReindexTimer();
    this.reindexRequest?.abort();
    this.reindexRequest = null;
    this.reindexConfigId = null;
    this.reindexStatus = null;
    this.reindexErrorMessage = null;
    this.isReindexStatusLoading = false;
    this.isReindexing = false;
  }

  private clearReindexTimer(): void {
    if (this.reindexTimer !== null) {
      clearTimeout(this.reindexTimer);
      this.reindexTimer = null;
    }
  }

  private scheduleReindexStatusRefresh(configId: string): void {
    this.clearReindexTimer();
    this.reindexTimer = setTimeout(() => {
      void this.loadReindexStatus(configId);
    }, REINDEX_POLL_INTERVAL_MS);
  }
}

function shouldPoll(status: MemoryReindexStatus): boolean {
  return (
    status.state === "reindexing" ||
    status.latest_job?.state === "pending" ||
    status.latest_job?.state === "running"
  );
}

function buildContextKey(
  organizationId: string,
  request: MemoryListRequest,
): string {
  return JSON.stringify({
    direction: request.direction,
    integrities: request.integrities,
    levels: request.levels,
    organizationId,
    query: request.query,
    recalled: request.recalled,
    sort: request.sort,
    statuses: request.statuses,
  });
}

function message(error: unknown, fallback: string): string {
  return error instanceof MemoryServiceError ? error.message : fallback;
}

export { MemoryStore };
