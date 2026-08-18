import { makeAutoObservable, runInAction } from "mobx";

import {
  SwarmDraftStorage,
  type StoredSwarmDraft,
  type SwarmDraftContext,
} from "@/features/swarms/swarm-draft-storage";
import {
  SwarmsService,
  SwarmsServiceError,
} from "@/features/swarms/swarms.service";
import type { Swarm, SwarmFormValues } from "@/features/swarms/swarms.types";

type SwarmFormField = keyof SwarmFormValues;

const DRAFT_ERROR =
  "This browser could not save the local draft. Keep this tab open until the Swarm is saved.";

class SwarmFormStore {
  draftStorageErrorMessage: string | null = null;
  errorMessage: string | null = null;
  fieldErrors: Partial<Record<SwarmFormField, string>> = {};
  hasLocalDraft = false;
  isLoading = false;
  isSubmitting = false;
  savedAt: string | null = null;
  serverSwarm: Swarm | null = null;
  successMessage: string | null = null;
  values: SwarmFormValues = emptyValues();

  private baselineValues: SwarmFormValues = emptyValues();
  private context: SwarmDraftContext | null = null;
  private contextKey: string | null = null;
  private readonly service: SwarmsService;
  private readonly storage: SwarmDraftStorage;

  constructor(service: SwarmsService, storage: SwarmDraftStorage) {
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
    return JSON.stringify(this.values) !== JSON.stringify(this.baselineValues);
  }

  isActiveFor(context: SwarmDraftContext): boolean {
    return this.contextKey === buildContextKey(context);
  }

  beginCreate(context: Omit<SwarmDraftContext, "mode" | "swarmId">): void {
    const next = { ...context, mode: "create" as const, swarmId: null };
    if (this.contextKey === buildContextKey(next)) return;
    this.reset(next);
    const draft = this.storage.read(next);
    if (draft !== null) this.applyDraft(draft);
  }

  startNew(context: Omit<SwarmDraftContext, "mode" | "swarmId">): void {
    const next = { ...context, mode: "create" as const, swarmId: null };
    this.storage.clear(next);
    this.reset(next);
  }

  async beginEdit(
    context: Omit<SwarmDraftContext, "mode"> & { swarmId: string },
  ): Promise<void> {
    const next = { ...context, mode: "edit" as const };
    const key = buildContextKey(next);
    if (this.contextKey === key) return;
    this.reset(next);
    this.isLoading = true;
    try {
      const swarm = await this.service.getSwarm(
        next.organizationId,
        next.swarmId,
      );
      if (this.contextKey !== key) return;
      runInAction(() => {
        this.serverSwarm = swarm;
        this.baselineValues = valuesFromSwarm(swarm);
        this.values = { ...this.baselineValues };
        const draft = this.storage.read(next);
        if (draft !== null) this.applyDraft(draft);
      });
    } catch (error) {
      if (this.contextKey === key) {
        runInAction(() => {
          this.errorMessage =
            error instanceof SwarmsServiceError
              ? error.message
              : "This Swarm could not be loaded. It may no longer exist.";
        });
      }
    } finally {
      if (this.contextKey === key) {
        runInAction(() => {
          this.isLoading = false;
        });
      }
    }
  }

  setField<Field extends SwarmFormField>(
    field: Field,
    value: SwarmFormValues[Field],
  ): void {
    this.values = { ...this.values, [field]: value };
    const errors = { ...this.fieldErrors };
    delete errors[field];
    this.fieldErrors = errors;
    this.errorMessage = null;
    this.successMessage = null;
    this.persistDraft();
  }

  discardLocalDraft(): void {
    if (this.context === null) return;
    this.storage.clear(this.context);
    this.values = { ...this.baselineValues };
    this.fieldErrors = {};
    this.errorMessage = null;
    this.successMessage = null;
    this.draftStorageErrorMessage = null;
    this.hasLocalDraft = false;
    this.savedAt = null;
  }

  synchronizeServerSwarm(swarm: Swarm): void {
    if (
      this.context?.mode !== "edit" ||
      this.context.swarmId !== swarm.id ||
      this.context.organizationId !== swarm.organizationId
    ) {
      return;
    }
    this.serverSwarm = swarm;
  }

  async submit(): Promise<Swarm | null> {
    if (this.context === null || this.isSubmitting) return null;
    const fieldErrors = validateValues(this.values);
    if (Object.keys(fieldErrors).length > 0) {
      this.fieldErrors = fieldErrors;
      this.errorMessage = "Review the highlighted Swarm details before saving.";
      return null;
    }
    if (this.context.mode === "edit" && this.serverSwarm === null) return null;

    const context = this.context;
    const key = this.contextKey;
    this.isSubmitting = true;
    this.errorMessage = null;
    this.successMessage = null;
    this.fieldErrors = {};
    this.persistDraft();
    try {
      const swarm =
        context.mode === "create"
          ? await this.service.createSwarm(context.organizationId, {
              description: nullable(this.values.description),
              name: this.values.name.trim(),
            })
          : await this.service.updateSwarm(
              context.organizationId,
              context.swarmId ?? "",
              {
                description: this.values.description.trim(),
                expectedDraftVersion: this.serverSwarm?.draftVersion ?? 0,
                name: this.values.name.trim(),
              },
            );
      if (this.contextKey !== key) return null;
      runInAction(() => {
        this.storage.clear(context);
        if (context.mode === "create") {
          this.reset(context);
        } else {
          this.serverSwarm = swarm;
          this.values = valuesFromSwarm(swarm);
          this.baselineValues = { ...this.values };
          this.hasLocalDraft = false;
          this.savedAt = null;
          this.draftStorageErrorMessage = null;
          this.successMessage = "Swarm details saved.";
        }
      });
      return swarm;
    } catch (error) {
      if (this.contextKey === key) {
        runInAction(() => {
          this.errorMessage =
            error instanceof SwarmsServiceError
              ? error.message
              : "The Swarm could not be saved. Try again.";
        });
      }
      return null;
    } finally {
      if (this.contextKey === key) {
        runInAction(() => {
          this.isSubmitting = false;
        });
      }
    }
  }

  private applyDraft(draft: StoredSwarmDraft): void {
    this.values = { ...draft.values };
    this.hasLocalDraft = true;
    this.savedAt = draft.savedAt;
  }

  private persistDraft(): void {
    if (this.context === null) return;
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
    this.draftStorageErrorMessage = saved ? null : DRAFT_ERROR;
  }

  private reset(context: SwarmDraftContext): void {
    this.context = context;
    this.contextKey = buildContextKey(context);
    this.baselineValues = emptyValues();
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.hasLocalDraft = false;
    this.isLoading = false;
    this.isSubmitting = false;
    this.savedAt = null;
    this.serverSwarm = null;
    this.successMessage = null;
    this.values = emptyValues();
  }
}

function emptyValues(): SwarmFormValues {
  return { description: "", name: "" };
}

function valuesFromSwarm(swarm: Swarm): SwarmFormValues {
  return { description: swarm.description ?? "", name: swarm.name };
}

function validateValues(
  values: SwarmFormValues,
): Partial<Record<SwarmFormField, string>> {
  const errors: Partial<Record<SwarmFormField, string>> = {};
  const name = values.name.trim();
  if (name === "") errors.name = "Enter a Swarm name.";
  else if (name.length > 100) errors.name = "Use 100 characters or fewer.";
  if (values.description.length > 2_000) {
    errors.description = "Use 2,000 characters or fewer.";
  }
  return errors;
}

function nullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function buildContextKey(context: SwarmDraftContext): string {
  return [
    context.memberKey,
    context.organizationId,
    context.mode,
    context.swarmId,
  ].join(":");
}

export { SwarmFormStore };
