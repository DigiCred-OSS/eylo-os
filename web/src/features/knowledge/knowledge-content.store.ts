import { makeAutoObservable, runInAction } from "mobx";

import {
  KnowledgeContentDraftStorage,
  type CorpusImportDraftValues,
  type InlineContentDraftValues,
  type KnowledgeContentDraftContext,
} from "@/features/knowledge/knowledge-content-draft-storage";
import {
  KnowledgeService,
  KnowledgeServiceError,
} from "@/features/knowledge/knowledge.service";
import type {
  CorpusImport,
  IngestionJob,
  KnowledgeDurableState,
  StorageConfig,
} from "@/features/knowledge/knowledge.types";

const WORK_LOAD_ERROR = "Durable Knowledge work could not be loaded.";
const STORAGE_LOAD_ERROR =
  "Storage configurations could not be loaded for corpus import.";
const INLINE_SUBMIT_ERROR =
  "The document could not be accepted. Review the content and try again.";
const CORPUS_SUBMIT_ERROR =
  "The corpus import could not be accepted. Review the storage settings and try again.";
const CANCEL_ERROR = "The work could not be cancelled. Refresh its state.";
const DRAFT_STORAGE_ERROR =
  "This browser could not save the content draft. Keep this dialog open until the work is accepted.";
const TERMINAL_STATES = new Set<KnowledgeDurableState>([
  "cancelled",
  "failed",
  "succeeded",
]);
const POLL_INTERVAL_MS = 2_000;

type InlineField = keyof InlineContentDraftValues;
type CorpusField = keyof CorpusImportDraftValues;

class KnowledgeContentStore {
  actingIds = new Set<string>();
  corpusDraftStorageErrorMessage: string | null = null;
  corpusErrorMessage: string | null = null;
  corpusImports: CorpusImport[] = [];
  corpusSavedAt: string | null = null;
  corpusValues: CorpusImportDraftValues = emptyCorpusValues();
  hasCorpusDraft = false;
  hasInlineDraft = false;
  hasLoaded = false;
  inlineDraftStorageErrorMessage: string | null = null;
  inlineErrorMessage: string | null = null;
  inlineSavedAt: string | null = null;
  inlineValues: InlineContentDraftValues = emptyInlineValues();
  isLoading = false;
  isSubmittingCorpus = false;
  isSubmittingInline = false;
  jobs: IngestionJob[] = [];
  storageConfigs: StorageConfig[] = [];
  storageErrorMessage: string | null = null;
  workErrorMessage: string | null = null;

  private context: KnowledgeContentDraftContext | null = null;
  private contextKey: string | null = null;
  private readonly drafts: KnowledgeContentDraftStorage;
  private isActive = false;
  private pollTimer: number | null = null;
  private refreshRequest: AbortController | null = null;
  private readonly service: KnowledgeService;

  constructor(service: KnowledgeService, drafts: KnowledgeContentDraftStorage) {
    this.service = service;
    this.drafts = drafts;
    makeAutoObservable<
      this,
      | "context"
      | "contextKey"
      | "drafts"
      | "isActive"
      | "pollTimer"
      | "refreshRequest"
      | "service"
    >(
      this,
      {
        context: false,
        contextKey: false,
        drafts: false,
        isActive: false,
        pollTimer: false,
        refreshRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get hasActiveWork(): boolean {
    return (
      this.jobs.some((job) => !TERMINAL_STATES.has(job.state)) ||
      this.corpusImports.some((item) => !TERMINAL_STATES.has(item.state))
    );
  }

  get isMonitoring(): boolean {
    return this.isActive && this.hasActiveWork;
  }

  get readyStorageConfigs(): StorageConfig[] {
    return this.storageConfigs.filter(
      (config) =>
        config.ready &&
        config.capabilities.list &&
        config.capabilities.download,
    );
  }

  async activate(context: KnowledgeContentDraftContext): Promise<void> {
    const nextKey = buildContextKey(context);
    if (this.contextKey !== nextKey) {
      this.reset(context, nextKey);
      this.restoreDrafts();
    }
    this.isActive = true;
    await Promise.all([this.refresh(), this.loadStorageConfigs()]);
  }

  stop(): void {
    this.isActive = false;
    this.refreshRequest?.abort();
    this.refreshRequest = null;
    this.clearPollTimer();
    this.isLoading = false;
  }

  async refresh(): Promise<void> {
    if (!this.isActive || this.context === null) {
      return;
    }
    this.refreshRequest?.abort();
    const request = new AbortController();
    this.refreshRequest = request;
    const context = this.context;
    const contextKey = this.contextKey;
    this.isLoading = !this.hasLoaded;
    this.workErrorMessage = null;

    const [jobsResult, importsResult] = await Promise.allSettled([
      this.service.listIngestions(
        context.organizationId,
        context.knowledgebaseId,
        request.signal,
      ),
      this.service.listCorpusImports(
        context.organizationId,
        context.knowledgebaseId,
        request.signal,
      ),
    ]);

    if (
      request.signal.aborted ||
      !this.isActive ||
      this.contextKey !== contextKey
    ) {
      return;
    }
    runInAction(() => {
      if (jobsResult.status === "fulfilled") {
        this.jobs = newestFirst(jobsResult.value);
      }
      if (importsResult.status === "fulfilled") {
        this.corpusImports = newestFirst(importsResult.value);
      }
      this.workErrorMessage =
        jobsResult.status === "rejected" || importsResult.status === "rejected"
          ? WORK_LOAD_ERROR
          : null;
      this.hasLoaded = true;
      this.isLoading = false;
      this.refreshRequest = null;
      this.schedulePoll();
    });
  }

  setInlineField<Field extends InlineField>(
    field: Field,
    value: InlineContentDraftValues[Field],
  ): void {
    this.inlineValues = { ...this.inlineValues, [field]: value };
    this.inlineErrorMessage = null;
    this.persistInlineDraft();
  }

  setCorpusField<Field extends CorpusField>(
    field: Field,
    value: CorpusImportDraftValues[Field],
  ): void {
    this.corpusValues = { ...this.corpusValues, [field]: value };
    this.corpusErrorMessage = null;
    this.persistCorpusDraft();
  }

  discardInlineDraft(): void {
    if (this.context !== null) {
      this.drafts.clearInline(this.context);
    }
    this.inlineValues = emptyInlineValues();
    this.hasInlineDraft = false;
    this.inlineSavedAt = null;
    this.inlineDraftStorageErrorMessage = null;
    this.inlineErrorMessage = null;
  }

  discardCorpusDraft(): void {
    if (this.context !== null) {
      this.drafts.clearCorpus(this.context);
    }
    this.corpusValues = emptyCorpusValues();
    this.hasCorpusDraft = false;
    this.corpusSavedAt = null;
    this.corpusDraftStorageErrorMessage = null;
    this.corpusErrorMessage = null;
  }

  async submitInline(): Promise<IngestionJob | null> {
    if (this.context === null || this.isSubmittingInline) {
      return null;
    }
    const content = this.inlineValues.content;
    const title = this.inlineValues.title.trim();
    const sourceUri = this.inlineValues.sourceUri.trim();
    if (content.trim() === "") {
      this.inlineErrorMessage = "Document content is required.";
      return null;
    }
    if (content.length > 1_000_000) {
      this.inlineErrorMessage =
        "Document content must not exceed 1,000,000 characters.";
      return null;
    }
    if (title.length > 512 || sourceUri.length > 4_096) {
      this.inlineErrorMessage = INLINE_SUBMIT_ERROR;
      return null;
    }

    const context = this.context;
    const contextKey = this.contextKey;
    this.isSubmittingInline = true;
    this.inlineErrorMessage = null;
    this.persistInlineDraft();
    try {
      const job = await this.service.submitIngestion(
        context.organizationId,
        context.knowledgebaseId,
        {
          content,
          source_uri: sourceUri === "" ? null : sourceUri,
          title: title === "" ? null : title,
        },
      );
      if (this.contextKey !== contextKey) {
        return null;
      }
      runInAction(() => {
        this.jobs = upsertNewest(this.jobs, job);
        this.discardInlineDraft();
        this.schedulePoll();
      });
      return job;
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.inlineErrorMessage = serviceErrorMessage(
            error,
            INLINE_SUBMIT_ERROR,
          );
        });
      }
      return null;
    } finally {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.isSubmittingInline = false;
        });
      }
    }
  }

  async submitCorpus(): Promise<CorpusImport | null> {
    if (this.context === null || this.isSubmittingCorpus) {
      return null;
    }
    const configId = this.corpusValues.storageProviderConfigId;
    if (
      configId === null ||
      !this.readyStorageConfigs.some((config) => config.id === configId)
    ) {
      this.corpusErrorMessage =
        "Choose a ready storage configuration that can list and download objects.";
      return null;
    }
    const prefix = this.corpusValues.prefix.trim();
    if (prefix.length > 1_024) {
      this.corpusErrorMessage = "Prefix must be 1,024 characters or fewer.";
      return null;
    }

    const context = this.context;
    const contextKey = this.contextKey;
    this.isSubmittingCorpus = true;
    this.corpusErrorMessage = null;
    this.persistCorpusDraft();
    try {
      const corpusImport = await this.service.startCorpusImport(
        context.organizationId,
        context.knowledgebaseId,
        { prefix, storage_provider_config_id: configId },
      );
      if (this.contextKey !== contextKey) {
        return null;
      }
      runInAction(() => {
        this.corpusImports = upsertNewest(this.corpusImports, corpusImport);
        this.discardCorpusDraft();
        this.schedulePoll();
      });
      return corpusImport;
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.corpusErrorMessage = serviceErrorMessage(
            error,
            CORPUS_SUBMIT_ERROR,
          );
        });
      }
      return null;
    } finally {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.isSubmittingCorpus = false;
        });
      }
    }
  }

  async cancelJob(jobId: string): Promise<void> {
    if (this.context === null || this.actingIds.has(jobId)) {
      return;
    }
    const context = this.context;
    const contextKey = this.contextKey;
    this.actingIds.add(jobId);
    this.workErrorMessage = null;
    try {
      const job = await this.service.cancelIngestion(
        context.organizationId,
        context.knowledgebaseId,
        jobId,
      );
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.jobs = upsertNewest(this.jobs, job);
          this.schedulePoll();
        });
      }
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.workErrorMessage = serviceErrorMessage(error, CANCEL_ERROR);
        });
      }
    } finally {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.actingIds.delete(jobId);
        });
      }
    }
  }

  async cancelCorpus(importId: string): Promise<void> {
    if (this.context === null || this.actingIds.has(importId)) {
      return;
    }
    const context = this.context;
    const contextKey = this.contextKey;
    this.actingIds.add(importId);
    this.workErrorMessage = null;
    try {
      const corpusImport = await this.service.cancelCorpusImport(
        context.organizationId,
        context.knowledgebaseId,
        importId,
      );
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.corpusImports = upsertNewest(this.corpusImports, corpusImport);
          this.schedulePoll();
        });
      }
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.workErrorMessage = serviceErrorMessage(error, CANCEL_ERROR);
        });
      }
    } finally {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.actingIds.delete(importId);
        });
      }
    }
  }

  private async loadStorageConfigs(): Promise<void> {
    const contextKey = this.contextKey;
    try {
      const configs = await this.service.listStorageConfigs();
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.storageConfigs = configs;
          this.storageErrorMessage = null;
        });
      }
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.storageErrorMessage = serviceErrorMessage(
            error,
            STORAGE_LOAD_ERROR,
          );
        });
      }
    }
  }

  private restoreDrafts(): void {
    if (this.context === null) {
      return;
    }
    const inlineDraft = this.drafts.readInline(this.context);
    const corpusDraft = this.drafts.readCorpus(this.context);
    if (inlineDraft !== null) {
      this.inlineValues = inlineDraft.values;
      this.inlineSavedAt = inlineDraft.savedAt;
      this.hasInlineDraft = true;
    }
    if (corpusDraft !== null) {
      this.corpusValues = corpusDraft.values;
      this.corpusSavedAt = corpusDraft.savedAt;
      this.hasCorpusDraft = true;
    }
  }

  private persistInlineDraft(): void {
    if (this.context === null) {
      return;
    }
    if (inlineValuesEmpty(this.inlineValues)) {
      this.discardInlineDraft();
      return;
    }
    const savedAt = new Date().toISOString();
    const saved = this.drafts.writeInline(this.context, {
      savedAt,
      values: { ...this.inlineValues },
      version: 1,
    });
    this.hasInlineDraft = saved;
    this.inlineSavedAt = saved ? savedAt : this.inlineSavedAt;
    this.inlineDraftStorageErrorMessage = saved ? null : DRAFT_STORAGE_ERROR;
  }

  private persistCorpusDraft(): void {
    if (this.context === null) {
      return;
    }
    if (corpusValuesEmpty(this.corpusValues)) {
      this.discardCorpusDraft();
      return;
    }
    const savedAt = new Date().toISOString();
    const saved = this.drafts.writeCorpus(this.context, {
      savedAt,
      values: { ...this.corpusValues },
      version: 1,
    });
    this.hasCorpusDraft = saved;
    this.corpusSavedAt = saved ? savedAt : this.corpusSavedAt;
    this.corpusDraftStorageErrorMessage = saved ? null : DRAFT_STORAGE_ERROR;
  }

  private schedulePoll(): void {
    this.clearPollTimer();
    if (!this.isActive || !this.hasActiveWork) {
      return;
    }
    this.pollTimer = window.setTimeout(() => {
      this.pollTimer = null;
      void this.refresh();
    }, POLL_INTERVAL_MS);
  }

  private clearPollTimer(): void {
    if (this.pollTimer !== null) {
      window.clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private reset(
    context: KnowledgeContentDraftContext,
    contextKey: string,
  ): void {
    this.stop();
    this.context = context;
    this.contextKey = contextKey;
    this.actingIds.clear();
    this.corpusDraftStorageErrorMessage = null;
    this.corpusErrorMessage = null;
    this.corpusImports = [];
    this.corpusSavedAt = null;
    this.corpusValues = emptyCorpusValues();
    this.hasCorpusDraft = false;
    this.hasInlineDraft = false;
    this.hasLoaded = false;
    this.inlineDraftStorageErrorMessage = null;
    this.inlineErrorMessage = null;
    this.inlineSavedAt = null;
    this.inlineValues = emptyInlineValues();
    this.jobs = [];
    this.storageConfigs = [];
    this.storageErrorMessage = null;
    this.workErrorMessage = null;
  }
}

function emptyInlineValues(): InlineContentDraftValues {
  return { content: "", sourceUri: "", title: "" };
}

function emptyCorpusValues(): CorpusImportDraftValues {
  return { prefix: "", storageProviderConfigId: null };
}

function inlineValuesEmpty(values: InlineContentDraftValues): boolean {
  return (
    values.content === "" && values.sourceUri === "" && values.title === ""
  );
}

function corpusValuesEmpty(values: CorpusImportDraftValues): boolean {
  return values.prefix === "" && values.storageProviderConfigId === null;
}

function buildContextKey(context: KnowledgeContentDraftContext): string {
  return `${context.organizationId}:${context.knowledgebaseId}:${context.memberKey.toLowerCase()}`;
}

function newestFirst<Item extends { created_at: string }>(
  items: Item[],
): Item[] {
  return [...items].sort(
    (left, right) =>
      new Date(right.created_at).getTime() -
      new Date(left.created_at).getTime(),
  );
}

function upsertNewest<Item extends { created_at: string; id: string }>(
  items: Item[],
  item: Item,
): Item[] {
  return newestFirst([
    item,
    ...items.filter((candidate) => candidate.id !== item.id),
  ]);
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof KnowledgeServiceError ? error.message : fallback;
}

export { KnowledgeContentStore, TERMINAL_STATES };
