import { makeAutoObservable, observable, runInAction } from "mobx";

import { ProviderDraftStorage } from "@/features/providers/provider-draft-storage";
import {
  ProviderServiceError,
  ProvidersService,
} from "@/features/providers/providers.service";
import type {
  ProviderCapability,
  ProviderCapabilityDefinition,
  ProviderConfigCreateInput,
  ProviderConfigRecord,
  ProviderConfigUpdateInput,
  ProviderDefinition,
  ProviderDraftContext,
  ProviderFieldDefinition,
  ProviderFieldValue,
  ProviderFormMode,
  ProviderFormValues,
  ProviderWriteValues,
  StoredProviderDraft,
} from "@/features/providers/providers.types";

const FORM_LOAD_ERROR_MESSAGE =
  "This provider configuration could not be loaded. It may no longer exist.";
const FORM_SAVE_ERROR_MESSAGE =
  "The provider configuration could not be saved. Review the form and try again.";
const DRAFT_STORAGE_ERROR_MESSAGE =
  "This browser could not save the local draft. Keep this tab open until the configuration is saved.";

interface ProviderFormContext extends ProviderDraftContext {
  mode: ProviderFormMode;
}

class ProviderFormStore {
  capabilityDefinition: ProviderCapabilityDefinition | null = null;
  draftStorageErrorMessage: string | null = null;
  errorMessage: string | null = null;
  fieldErrors: Record<string, string> = {};
  hasLocalDraft = false;
  isLoading = false;
  isSubmitting = false;
  mode: ProviderFormMode | null = null;
  referenceErrorMessage: string | null = null;
  referenceOptions: Partial<
    Record<ProviderCapability, ProviderConfigRecord[]>
  > = {};
  savedAt: string | null = null;
  serverConfig: ProviderConfigRecord | null = null;
  values: ProviderFormValues = emptyValues();

  private baselineValues: ProviderFormValues = emptyValues();
  private context: ProviderFormContext | null = null;
  private contextKey: string | null = null;
  private readonly service: ProvidersService;
  private readonly storage: ProviderDraftStorage;

  constructor(service: ProvidersService, storage: ProviderDraftStorage) {
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
        contextKey: observable,
        service: false,
        storage: false,
      },
      { autoBind: true },
    );
  }

  get isDirty(): boolean {
    return JSON.stringify(this.values) !== JSON.stringify(this.baselineValues);
  }

  get providerDefinition(): ProviderDefinition | null {
    return (
      this.capabilityDefinition?.providers.find(
        (provider) => provider.id === this.values.provider,
      ) ?? null
    );
  }

  get fields(): ProviderFieldDefinition[] {
    return this.providerDefinition?.fields ?? [];
  }

  matchesContext(
    context: ProviderDraftContext,
    mode: ProviderFormMode,
  ): boolean {
    return this.contextKey === buildContextKey({ ...context, mode });
  }

  beginCreate(
    context: Omit<ProviderDraftContext, "configId">,
    definition: ProviderCapabilityDefinition,
  ): void {
    const nextContext: ProviderFormContext = {
      ...context,
      configId: null,
      mode: "create",
    };
    if (this.contextKey === buildContextKey(nextContext)) {
      return;
    }

    this.reset(nextContext, definition);
    const storedDraft = this.storage.read(nextContext);
    if (
      storedDraft !== null &&
      definition.providers.some(
        (provider) => provider.id === storedDraft.values.provider,
      )
    ) {
      this.applyStoredDraft(storedDraft);
      void this.loadReferences();
    }
  }

  startNew(
    context: Omit<ProviderDraftContext, "configId">,
    definition: ProviderCapabilityDefinition,
  ): void {
    const nextContext: ProviderFormContext = {
      ...context,
      configId: null,
      mode: "create",
    };
    this.storage.clear(nextContext);
    this.reset(nextContext, definition);
  }

  async beginEdit(
    context: Omit<ProviderDraftContext, "configId"> & { configId: string },
    definition: ProviderCapabilityDefinition,
  ): Promise<void> {
    const nextContext: ProviderFormContext = { ...context, mode: "edit" };
    const nextKey = buildContextKey(nextContext);
    if (
      this.contextKey === nextKey &&
      (this.isLoading || this.serverConfig !== null)
    ) {
      return;
    }

    this.reset(nextContext, definition);
    this.isLoading = true;

    try {
      const config = await this.service.get(
        nextContext.capability,
        context.configId,
      );
      if (this.contextKey !== nextKey) {
        return;
      }

      runInAction(() => {
        this.serverConfig = config;
        this.values = valuesFromConfig(config, definition);
        this.baselineValues = cloneValues(this.values);

        const storedDraft = this.storage.read(nextContext);
        if (
          storedDraft !== null &&
          storedDraft.values.provider === config.provider
        ) {
          this.applyStoredDraft(storedDraft);
        }
      });
      await this.loadReferences();
    } catch (error) {
      if (this.contextKey === nextKey) {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(
            error,
            FORM_LOAD_ERROR_MESSAGE,
          );
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

  selectProvider(providerId: string): void {
    if (
      this.mode !== "create" ||
      !this.capabilityDefinition?.providers.some(
        (provider) => provider.id === providerId,
      )
    ) {
      return;
    }

    this.values = { config: {}, name: this.values.name, provider: providerId };
    this.fieldErrors = {};
    this.errorMessage = null;
    this.referenceOptions = {};
    this.referenceErrorMessage = null;
    this.persistDraft();
    void this.loadReferences();
  }

  fieldIsVisible(field: ProviderFieldDefinition): boolean {
    return isFieldVisible(field, this.values.config);
  }

  hasStoredSecret(field: ProviderFieldDefinition): boolean {
    const value = this.serverConfig?.secrets[field.wire_key];
    return typeof value === "string" && value !== "";
  }

  setName(name: string): void {
    this.values = { ...this.values, name };
    this.clearFieldError("name");
    this.persistDraft();
  }

  setConfigField(key: string, value: ProviderFieldValue): void {
    if (!this.fields.some((field) => field.key === key && !field.secret)) {
      return;
    }
    this.values = {
      ...this.values,
      config: { ...this.values.config, [key]: value },
    };
    this.clearFieldError(key);
    this.persistDraft();
  }

  discardLocalDraft(): void {
    if (this.context === null) {
      return;
    }
    this.storage.clear(this.context);
    this.values = cloneValues(this.baselineValues);
    this.hasLocalDraft = false;
    this.savedAt = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.fieldErrors = {};
    void this.loadReferences();
  }

  async submit(
    transientSecrets: Record<string, string | null>,
  ): Promise<ProviderConfigRecord | null> {
    if (
      this.context === null ||
      this.mode === null ||
      this.providerDefinition === null ||
      this.isSubmitting
    ) {
      return null;
    }

    const writeValues: ProviderWriteValues = {
      ...cloneValues(this.values),
      secrets: { ...transientSecrets },
    };
    const context = this.context;
    const contextKey = this.contextKey;
    const mode = this.mode;
    const providerDefinition = this.providerDefinition;
    const errors = validateWriteValues(
      writeValues,
      providerDefinition,
      mode,
      this.serverConfig,
    );
    if (Object.keys(errors).length > 0) {
      this.fieldErrors = errors;
      this.errorMessage =
        "Complete the required provider settings before saving.";
      return null;
    }

    this.isSubmitting = true;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.persistDraft();

    try {
      const config =
        mode === "create"
          ? await this.service.create(
              context.capability,
              toCreateInput(writeValues, providerDefinition),
            )
          : await this.service.update(
              context.capability,
              context.configId ?? "",
              toUpdateInput(writeValues, providerDefinition),
            );
      if (this.contextKey !== contextKey) {
        return null;
      }

      runInAction(() => {
        this.acceptSavedConfig(config);
      });
      return config;
    } catch (error) {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.errorMessage = serviceErrorMessage(
            error,
            FORM_SAVE_ERROR_MESSAGE,
          );
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

  private async loadReferences(): Promise<void> {
    const requestKey = `${this.contextKey ?? ""}:${this.values.provider}`;
    const capabilities = [
      ...new Set(
        this.fields.flatMap((field) =>
          field.kind === "provider_config" && field.reference_capability != null
            ? [field.reference_capability]
            : [],
        ),
      ),
    ];
    if (capabilities.length === 0) {
      this.referenceOptions = {};
      this.referenceErrorMessage = null;
      return;
    }

    try {
      const entries = await Promise.all(
        capabilities.map(
          async (capability) =>
            [
              capability,
              (await this.service.list(capability)).filter(
                (config) => config.ready,
              ),
            ] as const,
        ),
      );
      if (`${this.contextKey ?? ""}:${this.values.provider}` !== requestKey) {
        return;
      }
      runInAction(() => {
        this.referenceOptions = Object.fromEntries(entries);
        this.referenceErrorMessage = null;
      });
    } catch (error) {
      if (`${this.contextKey ?? ""}:${this.values.provider}` !== requestKey) {
        return;
      }
      runInAction(() => {
        this.referenceOptions = {};
        this.referenceErrorMessage = serviceErrorMessage(
          error,
          "Required provider configurations could not be loaded.",
        );
      });
    }
  }

  private reset(
    context: ProviderFormContext,
    definition: ProviderCapabilityDefinition,
  ): void {
    this.context = context;
    this.contextKey = buildContextKey(context);
    this.capabilityDefinition = definition;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.fieldErrors = {};
    this.hasLocalDraft = false;
    this.isLoading = false;
    this.isSubmitting = false;
    this.mode = context.mode;
    this.referenceErrorMessage = null;
    this.referenceOptions = {};
    this.savedAt = null;
    this.serverConfig = null;
    this.values = emptyValues();
    this.baselineValues = emptyValues();
  }

  private applyStoredDraft(draft: StoredProviderDraft): void {
    this.values = cloneValues(draft.values);
    this.hasLocalDraft = true;
    this.savedAt = draft.savedAt;
  }

  private persistDraft(): void {
    if (this.context === null || this.providerDefinition === null) {
      return;
    }
    const savedAt = new Date().toISOString();
    const stored = this.storage.write(
      this.context,
      { savedAt, values: cloneValues(this.values), version: 1 },
      this.providerDefinition.fields,
    );
    this.hasLocalDraft = stored;
    this.savedAt = stored ? savedAt : null;
    this.draftStorageErrorMessage = stored ? null : DRAFT_STORAGE_ERROR_MESSAGE;
  }

  private acceptSavedConfig(config: ProviderConfigRecord): void {
    if (this.context !== null) {
      this.storage.clear(this.context);
    }
    if (
      this.mode === "create" &&
      this.context !== null &&
      this.capabilityDefinition !== null
    ) {
      this.reset(this.context, this.capabilityDefinition);
      return;
    }

    this.serverConfig = config;
    this.values = valuesFromConfig(
      config,
      this.capabilityDefinition ?? emptyCapabilityDefinition(config.capability),
    );
    this.baselineValues = cloneValues(this.values);
    this.hasLocalDraft = false;
    this.savedAt = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
    this.fieldErrors = {};
  }

  private clearFieldError(field: string): void {
    if (!(field in this.fieldErrors)) {
      return;
    }
    const remaining = { ...this.fieldErrors };
    delete remaining[field];
    this.fieldErrors = remaining;
    this.errorMessage = null;
  }
}

function validateWriteValues(
  values: ProviderWriteValues,
  provider: ProviderDefinition,
  mode: ProviderFormMode,
  serverConfig: ProviderConfigRecord | null,
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (values.name.trim() === "") {
    errors.name = "Name is required.";
  }

  for (const field of provider.fields) {
    if (!isFieldVisible(field, values.config)) {
      continue;
    }
    const required =
      field.required ||
      (field.required_when != null &&
        conditionMatches(field.required_when, values.config));
    const value = field.secret
      ? values.secrets[field.key]
      : values.config[field.key];
    const existingSecret = serverConfig?.secrets[field.wire_key];
    const hasExistingSecret =
      mode === "edit" &&
      typeof existingSecret === "string" &&
      existingSecret !== "";
    const mayUseExistingSecret = value === undefined && hasExistingSecret;
    if (required && !hasValue(value) && !mayUseExistingSecret) {
      errors[field.key] = `${field.label} is required.`;
      continue;
    }
    if (
      typeof value === "number" &&
      ((field.minimum != null && value < field.minimum) ||
        (field.maximum != null && value > field.maximum))
    ) {
      errors[field.key] = `${field.label} is outside the allowed range.`;
    }
  }

  for (const group of provider.require_one_of) {
    if (!group.some((key) => hasValue(values.config[key]))) {
      for (const key of group) {
        errors[key] = `Provide at least one of: ${group.join(", ")}.`;
      }
    }
  }
  return errors;
}

function toCreateInput(
  values: ProviderWriteValues,
  provider: ProviderDefinition,
): ProviderConfigCreateInput {
  return {
    config: buildConfig(values, provider),
    name: values.name.trim(),
    provider: values.provider,
    secrets: buildCreateSecrets(values, provider),
  };
}

function toUpdateInput(
  values: ProviderWriteValues,
  provider: ProviderDefinition,
): ProviderConfigUpdateInput {
  const secrets = buildSecrets(values, provider, true);
  return {
    config: buildConfig(values, provider),
    name: values.name.trim(),
    ...(Object.keys(secrets).length > 0 ? { secrets } : {}),
  };
}

function buildConfig(
  values: ProviderWriteValues,
  provider: ProviderDefinition,
): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  for (const field of provider.fields) {
    if (field.target !== "config" || !isFieldVisible(field, values.config)) {
      continue;
    }
    const value = values.config[field.key];
    if (hasValue(value)) {
      config[field.wire_key] = value;
    }
  }
  return config;
}

function buildCreateSecrets(
  values: ProviderWriteValues,
  provider: ProviderDefinition,
): Record<string, string> {
  const secrets: Record<string, string> = {};
  for (const [key, value] of Object.entries(
    buildSecrets(values, provider, false),
  )) {
    if (value !== null) {
      secrets[key] = value;
    }
  }
  return secrets;
}

function buildSecrets(
  values: ProviderWriteValues,
  provider: ProviderDefinition,
  includeNull: boolean,
): Record<string, string | null> {
  const secrets: Record<string, string | null> = {};
  for (const field of provider.fields) {
    if (field.target !== "secrets" || !isFieldVisible(field, values.config)) {
      continue;
    }
    const value = values.secrets[field.key];
    if (value === null && includeNull) {
      secrets[field.wire_key] = null;
    } else if (typeof value === "string" && value !== "") {
      secrets[field.wire_key] = value;
    }
  }
  return secrets;
}

function valuesFromConfig(
  config: ProviderConfigRecord,
  definition: ProviderCapabilityDefinition,
): ProviderFormValues {
  const provider = definition.providers.find(
    (candidate) => candidate.id === config.provider,
  );
  const values: Record<string, ProviderFieldValue> = {};
  for (const field of provider?.fields ?? []) {
    if (field.target !== "config") {
      continue;
    }
    values[field.key] = toFieldValue(config.config[field.wire_key]);
  }
  return { config: values, name: config.name, provider: config.provider };
}

function toFieldValue(value: unknown): ProviderFieldValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
    return value;
  }
  return null;
}

function isFieldVisible(
  field: ProviderFieldDefinition,
  config: Record<string, ProviderFieldValue>,
): boolean {
  return conditionMatches(field.visible_when, config);
}

function conditionMatches(
  condition: ProviderFieldDefinition["visible_when"],
  config: Record<string, ProviderFieldValue>,
): boolean {
  return condition == null || config[condition.field] === condition.equals;
}

function hasValue(value: ProviderFieldValue | string | undefined): boolean {
  if (typeof value === "string") {
    return value.trim() !== "";
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  return value !== null && value !== undefined;
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ProviderServiceError ? error.message : fallback;
}

function emptyValues(): ProviderFormValues {
  return { config: {}, name: "", provider: "" };
}

function cloneValues(values: ProviderFormValues): ProviderFormValues {
  return {
    config: Object.fromEntries(
      Object.entries(values.config).map(([key, value]) => [
        key,
        Array.isArray(value) ? [...value] : value,
      ]),
    ),
    name: values.name,
    provider: values.provider,
  };
}

function buildContextKey(context: ProviderFormContext): string {
  return [
    context.memberKey,
    context.organizationId,
    context.capability,
    context.mode,
    context.configId ?? "new",
  ].join(":");
}

function emptyCapabilityDefinition(
  capability: ProviderCapability,
): ProviderCapabilityDefinition {
  return {
    capability,
    configure_via: "",
    description: "",
    label: "",
    providers: [],
  };
}

export { ProviderFormStore };
