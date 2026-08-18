import { makeAutoObservable, runInAction } from "mobx";

import {
  KnowledgeDraftStorage,
  type KnowledgeDraftContext,
  type StoredKnowledgeDraft,
} from "@/features/knowledge/knowledge-draft-storage";
import {
  KnowledgeService,
  KnowledgeServiceError,
} from "@/features/knowledge/knowledge.service";
import {
  KNOWLEDGE_SCOPES,
  KNOWLEDGE_VENDORS,
  type EmbeddingConfig,
  type KnowledgeAgentOption,
  type Knowledgebase,
  type KnowledgebaseCreateInput,
  type KnowledgebaseFormMode,
  type KnowledgebaseFormValues,
  type KnowledgebaseUpdateInput,
  type KnowledgeScope,
  type KnowledgeVendor,
} from "@/features/knowledge/knowledge.types";

const FORM_LOAD_ERROR =
  "This knowledgebase could not be loaded. It may no longer exist.";
const FORM_SAVE_ERROR =
  "The knowledgebase could not be saved. Review the form and try again.";
const DRAFT_STORAGE_ERROR =
  "This browser could not save the local draft. Keep this tab open until the knowledgebase is saved.";

type KnowledgeFormField = keyof KnowledgebaseFormValues;
type KnowledgeFormContext = KnowledgeDraftContext;

class KnowledgeFormStore {
  agentOptions: KnowledgeAgentOption[] = [];
  draftStorageErrorMessage: string | null = null;
  embeddingConfigs: EmbeddingConfig[] = [];
  errorMessage: string | null = null;
  fieldErrors: Partial<Record<KnowledgeFormField, string>> = {};
  hasLocalDraft = false;
  isLoading = false;
  isReferencesLoading = false;
  isSubmitting = false;
  mode: KnowledgebaseFormMode | null = null;
  referenceErrorMessage: string | null = null;
  savedAt: string | null = null;
  serverKnowledgebase: Knowledgebase | null = null;
  values: KnowledgebaseFormValues = emptyValues();

  private baselineValues: KnowledgebaseFormValues = emptyValues();
  private context: KnowledgeFormContext | null = null;
  private contextKey: string | null = null;
  private readonly service: KnowledgeService;
  private readonly storage: KnowledgeDraftStorage;

  constructor(service: KnowledgeService, storage: KnowledgeDraftStorage) {
    this.service = service;
    this.storage = storage;
    makeAutoObservable<
      this,
      "baselineValues" | "context" | "contextKey" | "service" | "storage"
    >(
      this,
      {
        baselineValues: false,
        context: false,
        contextKey: false,
        service: false,
        storage: false,
      },
      { autoBind: true },
    );
  }

  get isDirty(): boolean {
    return !formValuesEqual(this.values, this.baselineValues);
  }

  get readyEmbeddingConfigs(): EmbeddingConfig[] {
    return this.embeddingConfigs.filter((config) => config.ready);
  }

  beginCreate(
    context: Omit<KnowledgeFormContext, "knowledgebaseId" | "mode">,
  ): void {
    const nextContext: KnowledgeFormContext = {
      ...context,
      knowledgebaseId: null,
      mode: "create",
    };
    if (this.contextKey === buildContextKey(nextContext)) {
      return;
    }

    this.reset(nextContext);
    const draft = this.storage.read(nextContext);
    if (draft !== null) {
      this.applyStoredDraft(draft);
    }
    void this.loadReferences(nextContext.organizationId);
  }

  async beginEdit(
    context: Omit<KnowledgeFormContext, "mode"> & {
      knowledgebaseId: string;
    },
  ): Promise<void> {
    const nextContext: KnowledgeFormContext = { ...context, mode: "edit" };
    const nextContextKey = buildContextKey(nextContext);
    if (this.contextKey === nextContextKey) {
      return;
    }

    this.reset(nextContext);
    this.isLoading = true;
    void this.loadReferences(nextContext.organizationId);

    try {
      const knowledgebase = await this.service.getKnowledgebase(
        nextContext.organizationId,
        context.knowledgebaseId,
      );
      if (this.contextKey !== nextContextKey) {
        return;
      }
      runInAction(() => {
        this.serverKnowledgebase = knowledgebase;
        this.baselineValues = valuesFromKnowledgebase(knowledgebase);
        this.values = { ...this.baselineValues };
        const draft = this.storage.read(nextContext);
        if (draft !== null) {
          this.applyStoredDraft(draft);
        }
      });
    } catch (error) {
      if (this.contextKey === nextContextKey) {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(error, FORM_LOAD_ERROR);
        });
      }
    } finally {
      if (this.contextKey === nextContextKey) {
        runInAction(() => {
          this.isLoading = false;
        });
      }
    }
  }

  setField<Field extends KnowledgeFormField>(
    field: Field,
    value: KnowledgebaseFormValues[Field],
  ): void {
    this.values = { ...this.values, [field]: value };
    this.clearFieldError(field);
    this.persistDraft();
  }

  setVendor(vendor: KnowledgeVendor): void {
    if (this.mode !== "create" || !KNOWLEDGE_VENDORS.includes(vendor)) {
      return;
    }
    this.values = {
      ...this.values,
      embeddingProviderConfigId:
        vendor === "pgvector" ? this.values.embeddingProviderConfigId : null,
      vendor,
    };
    this.clearFieldError("vendor");
    this.clearFieldError("embeddingProviderConfigId");
    this.persistDraft();
  }

  setScope(scope: KnowledgeScope): void {
    if (this.mode !== "create" || !KNOWLEDGE_SCOPES.includes(scope)) {
      return;
    }
    this.values = {
      ...this.values,
      scope,
      scopeId:
        scope === "organization" ? (this.context?.organizationId ?? "") : "",
    };
    this.clearFieldError("scope");
    this.clearFieldError("scopeId");
    this.persistDraft();
  }

  discardLocalDraft(): void {
    if (this.context === null) {
      return;
    }
    this.storage.clear(this.context);
    this.values = { ...this.baselineValues };
    this.fieldErrors = {};
    this.errorMessage = null;
    this.draftStorageErrorMessage = null;
    this.hasLocalDraft = false;
    this.savedAt = null;
  }

  async reloadReferences(): Promise<void> {
    if (this.context !== null) {
      await this.loadReferences(this.context.organizationId);
    }
  }

  async submit(): Promise<Knowledgebase | null> {
    if (
      this.context === null ||
      this.mode === null ||
      this.isSubmitting ||
      (this.mode === "edit" && this.serverKnowledgebase === null)
    ) {
      return null;
    }

    const fieldErrors = validateValues(
      this.values,
      this.mode,
      this.context.organizationId,
      this.readyEmbeddingConfigs,
    );
    if (Object.keys(fieldErrors).length > 0) {
      this.fieldErrors = fieldErrors;
      this.errorMessage = "Review the highlighted settings before saving.";
      return null;
    }

    const context = this.context;
    const contextKey = this.contextKey;
    const mode = this.mode;
    this.isSubmitting = true;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.persistDraft();

    try {
      const knowledgebase =
        mode === "create"
          ? await this.service.createKnowledgebase(
              context.organizationId,
              toCreateInput(this.values, context.organizationId),
            )
          : await this.service.updateKnowledgebase(
              context.organizationId,
              context.knowledgebaseId ?? "",
              toUpdateInput(this.values),
            );
      if (this.contextKey !== contextKey) {
        return null;
      }
      runInAction(() => {
        this.acceptSavedKnowledgebase(knowledgebase);
      });
      return knowledgebase;
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(error, FORM_SAVE_ERROR);
        });
      }
      return null;
    } finally {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.isSubmitting = false;
        });
      }
    }
  }

  private async loadReferences(organizationId: string): Promise<void> {
    const requestContextKey = this.contextKey;
    this.isReferencesLoading = true;
    this.referenceErrorMessage = null;
    const [embeddingResult, agentResult] = await Promise.allSettled([
      this.service.listEmbeddingConfigs(),
      this.service.listAgentOptions(organizationId),
    ]);
    if (this.contextKey !== requestContextKey) {
      return;
    }
    runInAction(() => {
      if (embeddingResult.status === "fulfilled") {
        this.embeddingConfigs = embeddingResult.value;
      }
      if (agentResult.status === "fulfilled") {
        this.agentOptions = agentResult.value;
      }
      this.referenceErrorMessage =
        embeddingResult.status === "rejected" ||
        agentResult.status === "rejected"
          ? "Some scope or provider options could not be loaded."
          : null;
      this.isReferencesLoading = false;
    });
  }

  private acceptSavedKnowledgebase(knowledgebase: Knowledgebase): void {
    if (this.context !== null) {
      this.storage.clear(this.context);
    }
    this.serverKnowledgebase = knowledgebase;
    this.values = valuesFromKnowledgebase(knowledgebase);
    this.baselineValues = { ...this.values };
    this.hasLocalDraft = false;
    this.savedAt = null;
    this.draftStorageErrorMessage = null;
  }

  private applyStoredDraft(draft: StoredKnowledgeDraft): void {
    this.values = { ...draft.values };
    this.hasLocalDraft = true;
    this.savedAt = draft.savedAt;
  }

  private persistDraft(): void {
    if (this.context === null) {
      return;
    }
    if (!this.isDirty) {
      this.storage.clear(this.context);
      this.hasLocalDraft = false;
      this.savedAt = null;
      this.draftStorageErrorMessage = null;
      return;
    }
    const savedAt = new Date().toISOString();
    const saved = this.storage.write(this.context, {
      savedAt,
      values: { ...this.values },
      version: 1,
    });
    this.hasLocalDraft = saved;
    this.savedAt = saved ? savedAt : this.savedAt;
    this.draftStorageErrorMessage = saved ? null : DRAFT_STORAGE_ERROR;
  }

  private clearFieldError(field: KnowledgeFormField): void {
    const remaining = { ...this.fieldErrors };
    delete remaining[field];
    this.fieldErrors = remaining;
    this.errorMessage = null;
  }

  private reset(context: KnowledgeFormContext): void {
    this.context = context;
    this.contextKey = buildContextKey(context);
    this.mode = context.mode;
    this.agentOptions = [];
    this.embeddingConfigs = [];
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.hasLocalDraft = false;
    this.isLoading = false;
    this.isReferencesLoading = false;
    this.isSubmitting = false;
    this.referenceErrorMessage = null;
    this.savedAt = null;
    this.serverKnowledgebase = null;
    this.values = emptyValues();
    this.baselineValues = emptyValues();
  }
}

function emptyValues(): KnowledgebaseFormValues {
  return {
    chunkOverlap: "150",
    chunkSize: "1200",
    chunking: "paragraph",
    embeddingProviderConfigId: null,
    name: "",
    scope: "",
    scopeId: "",
    vendor: "",
    writable: false,
  };
}

function valuesFromKnowledgebase(
  knowledgebase: Knowledgebase,
): KnowledgebaseFormValues {
  return {
    chunkOverlap: String(knowledgebase.metadata?.chunk_overlap ?? 150),
    chunkSize: String(knowledgebase.metadata?.chunk_size ?? 1200),
    chunking: knowledgebase.metadata?.chunking ?? "paragraph",
    embeddingProviderConfigId: knowledgebase.embedding_provider_config_id,
    name: knowledgebase.name,
    scope: knowledgebase.scope,
    scopeId: knowledgebase.scope_id,
    vendor: asKnowledgeVendor(knowledgebase.vendor),
    writable: knowledgebase.writable,
  };
}

function validateValues(
  values: KnowledgebaseFormValues,
  mode: KnowledgebaseFormMode,
  organizationId: string,
  readyEmbeddingConfigs: readonly EmbeddingConfig[],
): Partial<Record<KnowledgeFormField, string>> {
  const errors: Partial<Record<KnowledgeFormField, string>> = {};
  const name = values.name.trim();
  if (name === "") {
    errors.name = "Name is required.";
  } else if (name.length > 128) {
    errors.name = "Name must be 128 characters or fewer.";
  }

  if (mode === "create") {
    if (values.vendor === "") {
      errors.vendor = "Choose a retrieval method.";
    }
    if (values.scope === "") {
      errors.scope = "Choose who this knowledge belongs to.";
    } else {
      const scopeId =
        values.scope === "organization"
          ? organizationId
          : values.scopeId.trim();
      if (!isUuid(scopeId)) {
        errors.scopeId =
          values.scope === "agent"
            ? "Choose an Agent."
            : "Enter a valid conversation ID.";
      }
    }
    if (
      values.vendor === "pgvector" &&
      (values.embeddingProviderConfigId === null ||
        !readyEmbeddingConfigs.some(
          (config) => config.id === values.embeddingProviderConfigId,
        ))
    ) {
      errors.embeddingProviderConfigId =
        "Choose a ready embedding provider configuration.";
    }
  }

  const chunkSize = parseInteger(values.chunkSize);
  const chunkOverlap = parseInteger(values.chunkOverlap);
  if (chunkSize === null || chunkSize < 80 || chunkSize > 32_000) {
    errors.chunkSize = "Chunk size must be an integer from 80 to 32,000.";
  }
  if (
    chunkOverlap === null ||
    chunkOverlap < 0 ||
    (chunkSize !== null && chunkOverlap >= chunkSize)
  ) {
    errors.chunkOverlap =
      "Overlap must be a non-negative integer smaller than chunk size.";
  }
  return errors;
}

function toCreateInput(
  values: KnowledgebaseFormValues,
  organizationId: string,
): KnowledgebaseCreateInput {
  const scope = values.scope as KnowledgeScope;
  return {
    embedding_provider_config_id:
      values.vendor === "pgvector" ? values.embeddingProviderConfigId : null,
    metadata: {
      chunk_overlap: Number(values.chunkOverlap),
      chunk_size: Number(values.chunkSize),
      chunking: values.chunking,
    },
    name: values.name.trim(),
    scope,
    scope_id: scope === "organization" ? organizationId : values.scopeId.trim(),
    vendor: values.vendor,
    writable: values.writable,
  };
}

function toUpdateInput(
  values: KnowledgebaseFormValues,
): KnowledgebaseUpdateInput {
  return {
    metadata: {
      chunk_overlap: Number(values.chunkOverlap),
      chunk_size: Number(values.chunkSize),
      chunking: values.chunking,
    },
    name: values.name.trim(),
    writable: values.writable,
  };
}

function formValuesEqual(
  left: KnowledgebaseFormValues,
  right: KnowledgebaseFormValues,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function buildContextKey(context: KnowledgeFormContext): string {
  return `${context.organizationId}:${context.mode}:${context.knowledgebaseId ?? "new"}:${context.memberKey.toLowerCase()}`;
}

function parseInteger(value: string): number | null {
  if (!/^-?\d+$/.test(value.trim())) {
    return null;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

function asKnowledgeVendor(vendor: string): KnowledgeVendor | "" {
  return KNOWLEDGE_VENDORS.includes(vendor as KnowledgeVendor)
    ? (vendor as KnowledgeVendor)
    : "";
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof KnowledgeServiceError ? error.message : fallback;
}

export { KnowledgeFormStore };
