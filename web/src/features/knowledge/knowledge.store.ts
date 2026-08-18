import { makeAutoObservable, runInAction } from "mobx";

import {
  KnowledgeService,
  KnowledgeServiceError,
} from "@/features/knowledge/knowledge.service";
import { KnowledgeContentDraftStorage } from "@/features/knowledge/knowledge-content-draft-storage";
import { KnowledgeContentStore } from "@/features/knowledge/knowledge-content.store";
import { KnowledgeDraftStorage } from "@/features/knowledge/knowledge-draft-storage";
import { KnowledgeFormStore } from "@/features/knowledge/knowledge-form.store";
import type {
  EmbeddingConfig,
  KnowledgeAgentOption,
  Knowledgebase,
  KnowledgeReindexStatus,
} from "@/features/knowledge/knowledge.types";

const COLLECTION_ERROR_MESSAGE =
  "Knowledgebases could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR_MESSAGE =
  "This knowledgebase could not be loaded. It may no longer exist.";
const DELETE_ERROR_MESSAGE =
  "The knowledgebase could not be deleted. Try again.";
const REINDEX_POLL_INTERVAL_MS = 2_000;

class KnowledgeStore {
  agentOptions: KnowledgeAgentOption[] = [];
  agentOptionsErrorMessage: string | null = null;
  collectionErrorMessage: string | null = null;
  deleteErrorMessage: string | null = null;
  hasLoadedCollection = false;
  isCollectionLoading = false;
  isDeleting = false;
  isAgentOptionsLoading = false;
  isReindexOptionsLoading = false;
  isReindexStatusLoading = false;
  isReindexing = false;
  isSelectedLoading = false;
  items: Knowledgebase[] = [];
  reindexEmbeddingConfigs: EmbeddingConfig[] = [];
  reindexErrorMessage: string | null = null;
  reindexOptionsErrorMessage: string | null = null;
  reindexStatus: KnowledgeReindexStatus | null = null;
  selectedErrorMessage: string | null = null;
  selectedKnowledgebase: Knowledgebase | null = null;

  readonly form: KnowledgeFormStore;
  readonly content: KnowledgeContentStore;

  private activeOrganizationId: string | null = null;
  private agentOptionsOrganizationId: string | null = null;
  private collectionRequest: AbortController | null = null;
  private reindexContextKey: string | null = null;
  private reindexRequest: AbortController | null = null;
  private reindexTimer: ReturnType<typeof setTimeout> | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: KnowledgeService;

  constructor(
    service: KnowledgeService,
    draftStorage: KnowledgeDraftStorage,
    contentDraftStorage: KnowledgeContentDraftStorage,
  ) {
    this.service = service;
    this.form = new KnowledgeFormStore(service, draftStorage);
    this.content = new KnowledgeContentStore(service, contentDraftStorage);
    makeAutoObservable<
      this,
      | "activeOrganizationId"
      | "agentOptionsOrganizationId"
      | "collectionRequest"
      | "reindexContextKey"
      | "reindexRequest"
      | "reindexTimer"
      | "selectedRequest"
      | "service"
    >(
      this,
      {
        activeOrganizationId: false,
        agentOptionsOrganizationId: false,
        collectionRequest: false,
        content: false,
        form: false,
        reindexContextKey: false,
        reindexRequest: false,
        reindexTimer: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get isCollectionStale(): boolean {
    return this.collectionErrorMessage !== null && this.items.length > 0;
  }

  async loadAgentOptions(organizationId: string, force = false): Promise<void> {
    if (
      !force &&
      this.agentOptionsOrganizationId === organizationId &&
      (this.isAgentOptionsLoading || this.agentOptions.length > 0)
    ) {
      return;
    }
    if (this.agentOptionsOrganizationId !== organizationId) {
      this.agentOptions = [];
      this.agentOptionsOrganizationId = organizationId;
    }
    this.isAgentOptionsLoading = true;
    this.agentOptionsErrorMessage = null;
    try {
      const options = await this.service.listAgentOptions(organizationId);
      if (this.agentOptionsOrganizationId === organizationId) {
        runInAction(() => {
          this.agentOptions = options;
        });
      }
    } catch (error) {
      if (this.agentOptionsOrganizationId === organizationId) {
        runInAction(() => {
          this.agentOptionsErrorMessage = serviceErrorMessage(
            error,
            "Agents could not be loaded for access configuration.",
          );
        });
      }
    } finally {
      if (this.agentOptionsOrganizationId === organizationId) {
        runInAction(() => {
          this.isAgentOptionsLoading = false;
        });
      }
    }
  }

  async loadCollection(organizationId: string): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    const contextChanged = this.activeOrganizationId !== organizationId;
    this.activeOrganizationId = organizationId;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    if (contextChanged) {
      this.items = [];
      this.clearSelected();
    }

    try {
      const items = await this.service.listKnowledgebases(
        organizationId,
        request.signal,
      );
      if (
        request.signal.aborted ||
        this.activeOrganizationId !== organizationId
      ) {
        return;
      }
      runInAction(() => {
        this.items = items;
        this.hasLoadedCollection = true;
      });
    } catch (error) {
      if (
        !request.signal.aborted &&
        this.activeOrganizationId === organizationId
      ) {
        runInAction(() => {
          this.collectionErrorMessage = serviceErrorMessage(
            error,
            COLLECTION_ERROR_MESSAGE,
          );
          this.hasLoadedCollection = true;
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
    knowledgebaseId: string,
  ): Promise<void> {
    this.selectedRequest?.abort();
    this.clearReindexState();
    const request = new AbortController();
    this.selectedRequest = request;
    this.selectedKnowledgebase =
      this.items.find((item) => item.id === knowledgebaseId) ?? null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;

    try {
      const knowledgebase = await this.service.getKnowledgebase(
        organizationId,
        knowledgebaseId,
        request.signal,
      );
      if (request.signal.aborted) {
        return;
      }
      runInAction(() => {
        this.selectedKnowledgebase = knowledgebase;
        this.upsertKnowledgebase(knowledgebase);
      });
      if (knowledgebase.vendor === "pgvector") {
        void this.loadReindexStatus(organizationId, knowledgebaseId);
      } else {
        this.clearReindexState();
      }
    } catch (error) {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.selectedKnowledgebase = null;
          this.selectedErrorMessage = serviceErrorMessage(
            error,
            DETAIL_ERROR_MESSAGE,
          );
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

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedKnowledgebase = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
    this.clearReindexState();
  }

  async loadReindexOptions(): Promise<void> {
    if (this.isReindexOptionsLoading) {
      return;
    }
    this.isReindexOptionsLoading = true;
    this.reindexOptionsErrorMessage = null;
    try {
      const configs = await this.service.listEmbeddingConfigs();
      runInAction(() => {
        this.reindexEmbeddingConfigs = configs.filter((config) => config.ready);
      });
    } catch (error) {
      runInAction(() => {
        this.reindexOptionsErrorMessage = serviceErrorMessage(
          error,
          "Ready embedding configurations could not be loaded.",
        );
      });
    } finally {
      runInAction(() => {
        this.isReindexOptionsLoading = false;
      });
    }
  }

  async loadReindexStatus(
    organizationId: string,
    knowledgebaseId: string,
  ): Promise<void> {
    this.clearReindexTimer();
    this.reindexRequest?.abort();
    const request = new AbortController();
    const contextKey = `${organizationId}:${knowledgebaseId}`;
    this.reindexRequest = request;
    this.reindexContextKey = contextKey;
    this.isReindexStatusLoading = true;

    try {
      const status = await this.service.getReindexStatus(
        organizationId,
        knowledgebaseId,
        request.signal,
      );
      if (request.signal.aborted || this.reindexContextKey !== contextKey) {
        return;
      }
      const shouldRefreshKnowledgebase =
        status.state === "active" &&
        this.selectedKnowledgebase?.id === knowledgebaseId &&
        this.selectedKnowledgebase.embedding_space_id !==
          status.active_space.space_id;
      runInAction(() => {
        this.reindexStatus = status;
        this.reindexErrorMessage = null;
      });
      if (shouldRefreshKnowledgebase) {
        const knowledgebase = await this.service.getKnowledgebase(
          organizationId,
          knowledgebaseId,
          request.signal,
        );
        if (!request.signal.aborted && this.reindexContextKey === contextKey) {
          runInAction(() => this.upsertKnowledgebase(knowledgebase));
        }
      }
      if (shouldPoll(status)) {
        this.scheduleReindexStatusRefresh(organizationId, knowledgebaseId);
      }
    } catch (error) {
      if (!request.signal.aborted && this.reindexContextKey === contextKey) {
        runInAction(() => {
          this.reindexErrorMessage = serviceErrorMessage(
            error,
            "Embedding index status could not be loaded.",
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

  async startKnowledgeReindex(
    organizationId: string,
    knowledgebaseId: string,
    embeddingProviderConfigId: string,
  ): Promise<boolean> {
    if (this.isReindexing) {
      return false;
    }
    const contextKey = `${organizationId}:${knowledgebaseId}`;
    this.isReindexing = true;
    this.reindexErrorMessage = null;
    try {
      await this.service.reindexKnowledgebase(
        organizationId,
        knowledgebaseId,
        embeddingProviderConfigId,
      );
      if (this.reindexContextKey !== contextKey) {
        return true;
      }
      await this.loadReindexStatus(organizationId, knowledgebaseId);
      return true;
    } catch (error) {
      if (this.reindexContextKey === contextKey) {
        runInAction(() => {
          this.reindexErrorMessage = serviceErrorMessage(
            error,
            "Reindex could not be started.",
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

  clearDeleteError(): void {
    this.deleteErrorMessage = null;
  }

  async deleteKnowledgebase(
    organizationId: string,
    knowledgebaseId: string,
  ): Promise<boolean> {
    if (this.isDeleting) {
      return false;
    }
    this.isDeleting = true;
    this.deleteErrorMessage = null;

    try {
      await this.service.deleteKnowledgebase(organizationId, knowledgebaseId);
      if (this.activeOrganizationId !== organizationId) {
        return false;
      }
      runInAction(() => {
        this.items = this.items.filter((item) => item.id !== knowledgebaseId);
        if (this.selectedKnowledgebase?.id === knowledgebaseId) {
          this.clearSelected();
        }
      });
      return true;
    } catch (error) {
      if (this.activeOrganizationId === organizationId) {
        runInAction(() => {
          this.deleteErrorMessage = serviceErrorMessage(
            error,
            DELETE_ERROR_MESSAGE,
          );
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.isDeleting = false;
      });
    }
  }

  upsertKnowledgebase(knowledgebase: Knowledgebase): void {
    const exists = this.items.some((item) => item.id === knowledgebase.id);
    this.items = exists
      ? this.items.map((item) =>
          item.id === knowledgebase.id ? knowledgebase : item,
        )
      : [...this.items, knowledgebase];
    if (this.selectedKnowledgebase?.id === knowledgebase.id) {
      this.selectedKnowledgebase = knowledgebase;
    }
  }

  private clearReindexState(): void {
    this.clearReindexTimer();
    this.reindexRequest?.abort();
    this.reindexRequest = null;
    this.reindexContextKey = null;
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

  private scheduleReindexStatusRefresh(
    organizationId: string,
    knowledgebaseId: string,
  ): void {
    this.clearReindexTimer();
    this.reindexTimer = setTimeout(() => {
      void this.loadReindexStatus(organizationId, knowledgebaseId);
    }, REINDEX_POLL_INTERVAL_MS);
  }
}

function shouldPoll(status: KnowledgeReindexStatus): boolean {
  return (
    status.state === "reindexing" ||
    status.latest_job?.state === "pending" ||
    status.latest_job?.state === "running"
  );
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof KnowledgeServiceError ? error.message : fallback;
}

export { KnowledgeStore };
