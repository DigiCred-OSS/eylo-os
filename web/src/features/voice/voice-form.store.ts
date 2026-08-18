import { makeAutoObservable, runInAction } from "mobx";

import type { ProviderReferencesStore } from "@/features/providers/provider-references.store";
import { VoiceConfigDraftStorage } from "@/features/voice/voice-draft-storage";
import {
  definitionFromValues,
  freshVoiceConfigValues,
  runtimeReadinessMessage,
  validateVoiceConfigValues,
  valuesFromVoiceConfig,
} from "@/features/voice/voice-form-values";
import {
  VoiceConfigService,
  VoiceConfigServiceError,
} from "@/features/voice/voice.service";
import type {
  StoredVoiceConfigDraft,
  VoiceConfigDraftContext,
  VoiceConfigFormMode,
  VoiceConfigFormValues,
  VoiceConfigRecord,
} from "@/features/voice/voice.types";

const LOAD_ERROR =
  "This Voice Config could not be loaded. It may no longer exist.";
const SAVE_ERROR =
  "The Voice Config could not be saved. Review the settings and try again.";
const DRAFT_ERROR =
  "This browser could not save the local draft. Keep this tab open until the Voice Config is saved.";
const CONFLICT_ERROR =
  "This Voice Config changed after your local draft began. Your input is preserved. Choose which version to continue from.";
const VOICE_PROVIDER_FIELDS = [
  "sttProviderConfigId",
  "ttsProviderConfigId",
  "realtimeProviderConfigId",
  "storageProviderConfigId",
] as const;

type VoiceConfigFormField = keyof VoiceConfigFormValues;

class VoiceConfigFormStore {
  baseRevision: number | null = null;
  conflictMessage: string | null = null;
  draftStorageErrorMessage: string | null = null;
  errorMessage: string | null = null;
  hasLocalDraft = false;
  isLoading = false;
  isSubmitting = false;
  mode: VoiceConfigFormMode | null = null;
  savedAt: string | null = null;
  serverVoiceConfig: VoiceConfigRecord | null = null;
  values: VoiceConfigFormValues = freshVoiceConfigValues();

  readonly references: ProviderReferencesStore;

  private baselineValues: VoiceConfigFormValues = freshVoiceConfigValues();
  private context: VoiceConfigDraftContext | null = null;
  private contextKey: string | null = null;
  private readonly service: VoiceConfigService;
  private readonly storage: VoiceConfigDraftStorage;

  constructor(
    service: VoiceConfigService,
    storage: VoiceConfigDraftStorage,
    references: ProviderReferencesStore,
  ) {
    this.service = service;
    this.storage = storage;
    this.references = references;
    makeAutoObservable<
      this,
      "baselineValues" | "context" | "contextKey" | "service" | "storage"
    >(
      this,
      {
        baselineValues: false,
        context: false,
        contextKey: false,
        references: false,
        service: false,
        storage: false,
      },
      { autoBind: true },
    );
  }

  get isDirty(): boolean {
    return !formValuesEqual(this.values, this.baselineValues);
  }

  get readinessMessage(): string | null {
    return runtimeReadinessMessage(this.values);
  }

  beginCreate(
    context: Omit<VoiceConfigDraftContext, "mode" | "voiceConfigId">,
  ): void {
    const nextContext: VoiceConfigDraftContext = {
      ...context,
      mode: "create",
      voiceConfigId: null,
    };
    if (this.contextKey === buildContextKey(nextContext)) {
      return;
    }
    this.reset(nextContext);
    const draft = this.storage.read(nextContext);
    if (draft !== null) {
      this.applyDraft(draft, null);
    }
    void this.references.loadAll(
      nextContext.organizationId,
      VOICE_PROVIDER_FIELDS,
    );
  }

  async beginEdit(
    context: Omit<VoiceConfigDraftContext, "mode"> & {
      voiceConfigId: string;
    },
  ): Promise<void> {
    const nextContext: VoiceConfigDraftContext = {
      ...context,
      mode: "edit",
    };
    const nextKey = buildContextKey(nextContext);
    if (this.contextKey === nextKey) {
      return;
    }
    this.reset(nextContext);
    this.isLoading = true;
    void this.references.loadAll(
      nextContext.organizationId,
      VOICE_PROVIDER_FIELDS,
    );
    try {
      const voiceConfig = await this.service.get(
        nextContext.organizationId,
        context.voiceConfigId,
      );
      if (this.contextKey !== nextKey) {
        return;
      }
      runInAction(() => {
        this.serverVoiceConfig = voiceConfig;
        this.baseRevision = voiceConfig.revision;
        this.baselineValues = valuesFromVoiceConfig(voiceConfig);
        this.values = { ...this.baselineValues };
        const draft = this.storage.read(nextContext);
        if (draft !== null) {
          this.applyDraft(draft, voiceConfig);
        }
      });
    } catch (error) {
      if (this.contextKey === nextKey) {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(error, LOAD_ERROR);
        });
      }
    } finally {
      if (this.contextKey === nextKey) {
        runInAction(() => {
          this.isLoading = false;
        });
      }
    }
  }

  setField<Field extends VoiceConfigFormField>(
    field: Field,
    value: VoiceConfigFormValues[Field],
  ): void {
    this.values = { ...this.values, [field]: value };
    this.errorMessage = null;
    this.persistDraft();
  }

  discardLocalDraft(): void {
    if (this.context === null) {
      return;
    }
    this.storage.clear(this.context);
    this.values =
      this.serverVoiceConfig === null
        ? freshVoiceConfigValues()
        : valuesFromVoiceConfig(this.serverVoiceConfig);
    this.baselineValues = { ...this.values };
    this.baseRevision = this.serverVoiceConfig?.revision ?? null;
    this.conflictMessage = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.hasLocalDraft = false;
    this.savedAt = null;
  }

  keepLocalChanges(): void {
    if (this.serverVoiceConfig === null) {
      return;
    }
    this.baseRevision = this.serverVoiceConfig.revision;
    this.baselineValues = valuesFromVoiceConfig(this.serverVoiceConfig);
    this.conflictMessage = null;
    this.persistDraft();
  }

  useServerVersion(): void {
    this.discardLocalDraft();
  }

  async submit(): Promise<VoiceConfigRecord | null> {
    if (
      this.context === null ||
      this.mode === null ||
      this.isSubmitting ||
      this.conflictMessage !== null ||
      (this.mode === "edit" &&
        (this.serverVoiceConfig === null || !this.isDirty))
    ) {
      return null;
    }
    const validationError = validateVoiceConfigValues(this.values);
    if (validationError !== null) {
      this.errorMessage = validationError;
      return null;
    }

    const context = this.context;
    const contextKey = this.contextKey;
    this.isSubmitting = true;
    this.errorMessage = null;
    this.persistDraft();

    try {
      const config = definitionFromValues(
        this.serverVoiceConfig?.config ?? null,
        this.values,
      );
      const saved =
        this.mode === "create"
          ? await this.service.create(context.organizationId, {
              config,
              description: optionalText(this.values.description),
              name: this.values.name.trim(),
            })
          : await this.service.update(
              context.organizationId,
              context.voiceConfigId ?? "",
              {
                config,
                description: optionalText(this.values.description),
                expected_revision: this.baseRevision ?? 0,
                name: this.values.name.trim(),
              },
            );
      if (this.contextKey !== contextKey) {
        return null;
      }
      runInAction(() => this.acceptSaved(saved));
      return saved;
    } catch (error) {
      if (this.contextKey !== contextKey) {
        return null;
      }
      if (error instanceof VoiceConfigServiceError && error.status === 409) {
        await this.enterConflict(context, contextKey);
      } else {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(error, SAVE_ERROR);
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

  private async enterConflict(
    context: VoiceConfigDraftContext,
    contextKey: string | null,
  ): Promise<void> {
    if (context.voiceConfigId === null) {
      return;
    }
    try {
      const latest = await this.service.get(
        context.organizationId,
        context.voiceConfigId,
      );
      if (this.contextKey !== contextKey) {
        return;
      }
      runInAction(() => {
        this.serverVoiceConfig = latest;
        this.conflictMessage = CONFLICT_ERROR;
        this.persistDraft();
      });
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(error, LOAD_ERROR);
        });
      }
    }
  }

  private acceptSaved(voiceConfig: VoiceConfigRecord): void {
    if (this.context !== null) {
      this.storage.clear(this.context);
    }
    this.serverVoiceConfig = voiceConfig;
    this.values = valuesFromVoiceConfig(voiceConfig);
    this.baselineValues = { ...this.values };
    this.baseRevision = voiceConfig.revision;
    this.conflictMessage = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.hasLocalDraft = false;
    this.savedAt = null;
  }

  private applyDraft(
    draft: StoredVoiceConfigDraft,
    serverVoiceConfig: VoiceConfigRecord | null,
  ): void {
    if (
      serverVoiceConfig !== null &&
      formValuesEqual(draft.values, valuesFromVoiceConfig(serverVoiceConfig))
    ) {
      if (this.context !== null) {
        this.storage.clear(this.context);
      }
      return;
    }
    this.values = { ...draft.values };
    this.baseRevision = draft.baseRevision;
    this.hasLocalDraft = true;
    this.savedAt = draft.savedAt;
    this.conflictMessage =
      serverVoiceConfig !== null &&
      draft.baseRevision !== serverVoiceConfig.revision
        ? CONFLICT_ERROR
        : null;
  }

  private persistDraft(): void {
    if (this.context === null) {
      return;
    }
    if (!this.isDirty && this.conflictMessage === null) {
      this.storage.clear(this.context);
      this.hasLocalDraft = false;
      this.savedAt = null;
      this.draftStorageErrorMessage = null;
      return;
    }
    const savedAt = new Date().toISOString();
    const saved = this.storage.write(this.context, {
      baseRevision: this.baseRevision,
      savedAt,
      values: this.values,
      version: 1,
    });
    if (saved) {
      this.hasLocalDraft = true;
      this.savedAt = savedAt;
      this.draftStorageErrorMessage = null;
    } else {
      this.draftStorageErrorMessage = DRAFT_ERROR;
    }
  }

  private reset(context: VoiceConfigDraftContext): void {
    this.context = context;
    this.contextKey = buildContextKey(context);
    this.mode = context.mode;
    this.baseRevision = null;
    this.baselineValues = freshVoiceConfigValues();
    this.values = freshVoiceConfigValues();
    this.conflictMessage = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.hasLocalDraft = false;
    this.isLoading = false;
    this.isSubmitting = false;
    this.savedAt = null;
    this.serverVoiceConfig = null;
  }
}

function formValuesEqual(
  left: VoiceConfigFormValues,
  right: VoiceConfigFormValues,
): boolean {
  return Object.keys(left).every((key) => {
    const field = key as VoiceConfigFormField;
    return left[field] === right[field];
  });
}

function optionalText(value: string): string | null {
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
}

function buildContextKey(context: VoiceConfigDraftContext): string {
  return [
    context.memberKey.toLowerCase(),
    context.organizationId,
    context.mode,
    context.voiceConfigId ?? "new",
  ].join(":");
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof VoiceConfigServiceError ? error.message : fallback;
}

export { VoiceConfigFormStore };
