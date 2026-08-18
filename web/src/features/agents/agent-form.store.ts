import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { getAgentApiErrorMessage } from "@/features/agents/agent-api-errors";
import type {
  AgentDraftContext,
  StoredAgentDraft,
} from "@/features/agents/agent-draft-storage";
import { AgentDraftStorage } from "@/features/agents/agent-draft-storage";
import { AgentReferencesStore } from "@/features/agents/agent-references.store";
import type {
  Agent,
  AgentCreateInput,
  AgentFormMode,
  AgentFormValues,
  AgentLlmOverrideValues,
  AgentUpdateInput,
} from "@/features/agents/agents.types";

const FORM_LOAD_ERROR_MESSAGE =
  "This Agent could not be loaded. It may no longer exist.";
const FORM_SAVE_ERROR_MESSAGE =
  "The Agent could not be saved. Review the form and try again.";
const DRAFT_STORAGE_ERROR_MESSAGE =
  "This browser could not save the local draft. Keep this tab open until the Agent is saved.";
const CONFLICT_MESSAGE =
  "This Agent changed after your local draft began. Your input is preserved. Choose which version to continue from.";

type AgentFormContext = AgentDraftContext;

class AgentFormStore {
  agentId: string | null = null;
  baseDraftVersion: number | null = null;
  conflictMessage: string | null = null;
  draftStorageErrorMessage: string | null = null;
  errorMessage: string | null = null;
  hasLocalDraft = false;
  isLoading = false;
  isSubmitting = false;
  mode: AgentFormMode | null = null;
  savedAt: string | null = null;
  serverAgent: Agent | null = null;
  values: AgentFormValues = createEmptyAgentFormValues();

  readonly references: AgentReferencesStore;

  private readonly api: ApiClient;
  private baselineValues: AgentFormValues = createEmptyAgentFormValues();
  private context: AgentFormContext | null = null;
  private contextKey: string | null = null;
  private readonly storage: AgentDraftStorage;

  constructor(
    api: ApiClient,
    storage: AgentDraftStorage,
    references: AgentReferencesStore,
  ) {
    this.api = api;
    this.storage = storage;
    this.references = references;

    makeAutoObservable<
      this,
      "api" | "baselineValues" | "context" | "contextKey" | "storage"
    >(
      this,
      {
        api: false,
        baselineValues: false,
        context: false,
        contextKey: false,
        references: false,
        storage: false,
      },
      { autoBind: true },
    );
  }

  get isDirty(): boolean {
    return !areFormValuesEqual(this.values, this.baselineValues);
  }

  matchesContext(organizationId: string, agentId: string | null): boolean {
    return (
      this.context?.organizationId === organizationId &&
      this.context.agentId === agentId
    );
  }

  matchesEditContext(organizationId: string, agentId: string): boolean {
    return (
      this.matchesContext(organizationId, agentId) &&
      this.context?.mode === "edit" &&
      this.context.agentId !== null
    );
  }

  beginCreate(context: Omit<AgentFormContext, "agentId" | "mode">): void {
    const nextContext: AgentFormContext = {
      ...context,
      agentId: null,
      mode: "create",
    };

    if (this.contextKey === buildContextKey(nextContext)) {
      return;
    }

    this.reset(nextContext);
    const storedDraft = this.storage.read(nextContext);

    if (storedDraft !== null) {
      this.applyStoredDraft(storedDraft, null);
    }

    void this.references.loadAll(nextContext.organizationId);
  }

  async beginEdit(context: Omit<AgentFormContext, "mode">): Promise<void> {
    const nextContext: AgentFormContext = { ...context, mode: "edit" };
    const nextContextKey = buildContextKey(nextContext);

    if (this.contextKey === nextContextKey) {
      return;
    }

    this.reset(nextContext);
    this.isLoading = true;
    void this.references.loadAll(nextContext.organizationId);

    const agent = await this.fetchAgent(
      nextContext.organizationId,
      nextContext.agentId ?? "",
    );

    if (this.contextKey !== nextContextKey) {
      return;
    }

    runInAction(() => {
      this.isLoading = false;

      if (agent === null) {
        this.errorMessage = FORM_LOAD_ERROR_MESSAGE;
        return;
      }

      this.serverAgent = agent;
      this.baseDraftVersion = agent.draftVersion;
      this.baselineValues = valuesFromAgent(agent);
      this.values = valuesFromAgent(agent);

      const storedDraft = this.storage.read(nextContext);
      if (storedDraft !== null) {
        this.applyStoredDraft(storedDraft, agent);
      }
    });
  }

  setField<Key extends keyof AgentFormValues>(
    field: Key,
    value: AgentFormValues[Key],
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
      this.serverAgent === null
        ? createEmptyAgentFormValues()
        : valuesFromAgent(this.serverAgent);
    this.baselineValues = { ...this.values };
    this.baseDraftVersion = this.serverAgent?.draftVersion ?? null;
    this.hasLocalDraft = false;
    this.savedAt = null;
    this.conflictMessage = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
  }

  keepLocalChanges(): void {
    if (this.serverAgent === null) {
      return;
    }

    this.baseDraftVersion = this.serverAgent.draftVersion;
    this.baselineValues = valuesFromAgent(this.serverAgent);
    this.conflictMessage = null;
    this.persistDraft();
  }

  useServerVersion(): void {
    this.discardLocalDraft();
  }

  synchronizeAfterRelatedWrite(agent: Agent): void {
    const latestValues = valuesFromAgent(agent);
    const serverFieldsChanged = !areFormValuesEqual(
      latestValues,
      this.baselineValues,
    );
    const hadLocalChanges = this.isDirty;

    this.serverAgent = agent;

    if (serverFieldsChanged && hadLocalChanges) {
      this.conflictMessage = CONFLICT_MESSAGE;
      this.persistDraft();
      return;
    }

    this.baselineValues = latestValues;
    this.baseDraftVersion = agent.draftVersion;

    if (!hadLocalChanges) {
      this.values = latestValues;
    }

    this.conflictMessage = null;
    this.persistDraft();
  }

  async submit(): Promise<Agent | null> {
    if (
      this.context === null ||
      this.mode === null ||
      this.isSubmitting ||
      this.conflictMessage !== null
    ) {
      return null;
    }

    if (this.values.name.trim() === "") {
      this.errorMessage = "Name is required.";
      return null;
    }
    if (
      this.values.allowFileUploads &&
      this.values.fileUploadEmbeddingProviderConfigId === null
    ) {
      this.errorMessage =
        "Choose a ready embedding config when file uploads are enabled.";
      return null;
    }
    if (
      this.values.kind === "BACKGROUND" &&
      this.values.voiceConfigId !== null
    ) {
      this.errorMessage =
        "Background Agents cannot bind a Voice Config. Choose a conversational Agent or clear Voice.";
      return null;
    }

    const llmOverrideError = validateLlmOverrides(this.values.llmOverrides);
    if (llmOverrideError !== null) {
      this.errorMessage = llmOverrideError;
      return null;
    }

    const context = this.context;
    const contextKey = this.contextKey;
    const mode = this.mode;

    this.isSubmitting = true;
    this.errorMessage = null;
    this.persistDraft();

    try {
      const result =
        mode === "create"
          ? await this.createAgent(context.organizationId)
          : await this.updateAgent(
              context.organizationId,
              context.agentId ?? "",
            );
      if (this.contextKey !== contextKey) {
        return null;
      }

      const savedAgent = result.agent;
      if (savedAgent !== null) {
        runInAction(() => {
          this.acceptSavedAgent(savedAgent);
        });
        return savedAgent;
      }

      if (result.status === 409 && mode === "edit") {
        await this.enterConflict(context, contextKey);
      } else {
        runInAction(() => {
          this.errorMessage = result.message;
        });
      }

      return null;
    } catch {
      if (this.contextKey === contextKey) {
        runInAction(() => {
          this.errorMessage = FORM_SAVE_ERROR_MESSAGE;
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

  private async createAgent(organizationId: string): Promise<SaveResult> {
    const { data, error, response } = await this.api.POST(
      "/api/{organization_id}/agents",
      {
        params: { path: { organization_id: organizationId } },
        body: toCreateInput(this.values),
      },
    );

    return toSaveResult(data, error, response);
  }

  private async updateAgent(
    organizationId: string,
    agentId: string,
  ): Promise<SaveResult> {
    if (this.baseDraftVersion === null) {
      return {
        agent: null,
        message: FORM_SAVE_ERROR_MESSAGE,
        status: 409,
      };
    }

    const { data, error, response } = await this.api.PATCH(
      "/api/{organization_id}/agents/{agent_id}",
      {
        params: {
          path: { organization_id: organizationId, agent_id: agentId },
        },
        body: toUpdateInput(this.values, this.baseDraftVersion),
      },
    );

    return toSaveResult(data, error, response);
  }

  private async enterConflict(
    context: AgentFormContext,
    contextKey: string | null,
  ): Promise<void> {
    if (context.agentId === null) {
      return;
    }

    const latestAgent = await this.fetchAgent(
      context.organizationId,
      context.agentId,
    );
    if (this.contextKey !== contextKey) {
      return;
    }

    runInAction(() => {
      if (latestAgent === null) {
        this.errorMessage = FORM_LOAD_ERROR_MESSAGE;
        return;
      }

      this.serverAgent = latestAgent;
      this.conflictMessage = CONFLICT_MESSAGE;
      this.persistDraft();
    });
  }

  private async fetchAgent(
    organizationId: string,
    agentId: string,
  ): Promise<Agent | null> {
    const { data, response } = await this.api.GET(
      "/api/{organization_id}/agents/{agent_id}",
      {
        params: {
          path: { organization_id: organizationId, agent_id: agentId },
        },
      },
    );

    return response.ok && data !== undefined ? data : null;
  }

  private acceptSavedAgent(agent: Agent): void {
    if (this.context !== null) {
      this.storage.clear(this.context);
    }

    this.serverAgent = agent;
    this.values = valuesFromAgent(agent);
    this.baselineValues = valuesFromAgent(agent);
    this.baseDraftVersion = agent.draftVersion;
    this.hasLocalDraft = false;
    this.savedAt = null;
    this.conflictMessage = null;
    this.draftStorageErrorMessage = null;
    this.errorMessage = null;
  }

  private applyStoredDraft(
    storedDraft: StoredAgentDraft,
    serverAgent: Agent | null,
  ): void {
    if (
      serverAgent !== null &&
      areFormValuesEqual(storedDraft.values, valuesFromAgent(serverAgent))
    ) {
      if (this.context !== null) {
        this.storage.clear(this.context);
      }
      return;
    }

    this.values = storedDraft.values;
    this.baseDraftVersion = storedDraft.baseDraftVersion;
    this.savedAt = storedDraft.savedAt;
    this.hasLocalDraft = true;
    this.conflictMessage =
      serverAgent !== null &&
      storedDraft.baseDraftVersion !== serverAgent.draftVersion
        ? CONFLICT_MESSAGE
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
      baseDraftVersion: this.baseDraftVersion,
      savedAt,
      values: this.values,
      version: 1,
    });

    if (saved) {
      this.hasLocalDraft = true;
      this.savedAt = savedAt;
      this.draftStorageErrorMessage = null;
    } else {
      this.draftStorageErrorMessage = DRAFT_STORAGE_ERROR_MESSAGE;
    }
  }

  private reset(context: AgentFormContext): void {
    this.context = context;
    this.contextKey = buildContextKey(context);
    this.agentId = context.agentId;
    this.mode = context.mode;
    this.values = createEmptyAgentFormValues();
    this.baselineValues = createEmptyAgentFormValues();
    this.baseDraftVersion = null;
    this.serverAgent = null;
    this.errorMessage = null;
    this.conflictMessage = null;
    this.draftStorageErrorMessage = null;
    this.hasLocalDraft = false;
    this.savedAt = null;
    this.isLoading = false;
    this.isSubmitting = false;
  }
}

interface SaveResult {
  agent: Agent | null;
  message: string;
  status: number;
}

function toSaveResult(
  data: Agent | undefined,
  error: unknown,
  response: Response,
): SaveResult {
  return response.ok && data !== undefined
    ? { agent: data, message: "", status: response.status }
    : {
        agent: null,
        message: getAgentApiErrorMessage(error, FORM_SAVE_ERROR_MESSAGE),
        status: response.status,
      };
}

function createEmptyAgentFormValues(): AgentFormValues {
  return {
    allowFileUploads: false,
    description: "",
    emailProviderConfigId: null,
    fileUploadEmbeddingProviderConfigId: null,
    instructionTemplateId: null,
    kind: "CONVERSATIONAL",
    llmOverrides: createEmptyLlmOverrides(),
    llmProviderConfigId: null,
    memoryProviderConfigId: null,
    name: "",
    rerankingProviderConfigId: null,
    voiceConfigId: null,
    webrtcProviderConfigId: null,
  };
}

function valuesFromAgent(agent: Agent): AgentFormValues {
  return {
    allowFileUploads: agent.allowFileUploads,
    description: agent.description ?? "",
    emailProviderConfigId: agent.emailProviderConfigId ?? null,
    fileUploadEmbeddingProviderConfigId:
      agent.fileUploadEmbeddingProviderConfigId ?? null,
    instructionTemplateId: agent.instructionTemplateId ?? null,
    kind: agent.kind,
    llmOverrides: normalizeLlmOverrides(agent.llmOverrides),
    llmProviderConfigId: agent.llmProviderConfigId ?? null,
    memoryProviderConfigId: agent.memoryProviderConfigId ?? null,
    name: agent.name,
    rerankingProviderConfigId: agent.rerankingProviderConfigId ?? null,
    voiceConfigId: agent.voiceConfigId ?? null,
    webrtcProviderConfigId: agent.webrtcProviderConfigId ?? null,
  };
}

function toCreateInput(values: AgentFormValues): AgentCreateInput {
  return {
    allowFileUploads: values.allowFileUploads,
    description: normalizeOptionalString(values.description),
    emailProviderConfigId: values.emailProviderConfigId,
    fileUploadEmbeddingProviderConfigId:
      values.fileUploadEmbeddingProviderConfigId,
    instructionTemplateId: values.instructionTemplateId,
    kind: values.kind,
    llmOverrides: toApiLlmOverrides(values.llmOverrides),
    llmProviderConfigId: values.llmProviderConfigId,
    memoryProviderConfigId: values.memoryProviderConfigId,
    name: values.name.trim(),
    rerankingProviderConfigId: values.rerankingProviderConfigId,
    voiceConfigId: values.voiceConfigId,
    webrtcProviderConfigId: values.webrtcProviderConfigId,
  };
}

function toUpdateInput(
  values: AgentFormValues,
  expectedDraftVersion: number,
): AgentUpdateInput {
  return {
    allowFileUploads: values.allowFileUploads,
    description: normalizeOptionalString(values.description),
    emailProviderConfigId: values.emailProviderConfigId,
    expectedDraftVersion,
    instructionTemplateId: values.instructionTemplateId,
    fileUploadEmbeddingProviderConfigId:
      values.fileUploadEmbeddingProviderConfigId,
    llmOverrides: toApiLlmOverrides(values.llmOverrides),
    llmProviderConfigId: values.llmProviderConfigId,
    memoryProviderConfigId: values.memoryProviderConfigId,
    name: values.name.trim(),
    rerankingProviderConfigId: values.rerankingProviderConfigId,
    voiceConfigId: values.voiceConfigId,
    webrtcProviderConfigId: values.webrtcProviderConfigId,
  };
}

function normalizeOptionalString(value: string): string | null {
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
}

function areFormValuesEqual(
  left: AgentFormValues,
  right: AgentFormValues,
): boolean {
  return Object.keys(left).every((key) => {
    const field = key as keyof AgentFormValues;
    if (field === "llmOverrides") {
      return areLlmOverridesEqual(left.llmOverrides, right.llmOverrides);
    }
    return left[field] === right[field];
  });
}

function createEmptyLlmOverrides(): AgentLlmOverrideValues {
  return {
    maxTokens: null,
    model: null,
    stopSequences: [],
    temperature: null,
    topK: null,
    topP: null,
  };
}

function normalizeLlmOverrides(
  overrides: Agent["llmOverrides"],
): AgentLlmOverrideValues {
  return {
    maxTokens: overrides?.maxTokens ?? null,
    model: overrides?.model ?? null,
    stopSequences: [...(overrides?.stopSequences ?? [])],
    temperature: overrides?.temperature ?? null,
    topK: overrides?.topK ?? null,
    topP: overrides?.topP ?? null,
  };
}

function toApiLlmOverrides(
  overrides: AgentLlmOverrideValues,
): AgentCreateInput["llmOverrides"] {
  return {
    maxTokens: overrides.maxTokens,
    model: overrides.model,
    stopSequences:
      overrides.stopSequences.length === 0 ? null : overrides.stopSequences,
    temperature: overrides.temperature,
    topK: overrides.topK,
    topP: overrides.topP,
  };
}

function areLlmOverridesEqual(
  left: AgentLlmOverrideValues,
  right: AgentLlmOverrideValues,
): boolean {
  return (
    left.maxTokens === right.maxTokens &&
    left.model === right.model &&
    left.temperature === right.temperature &&
    left.topK === right.topK &&
    left.topP === right.topP &&
    left.stopSequences.length === right.stopSequences.length &&
    left.stopSequences.every(
      (sequence, index) => sequence === right.stopSequences[index],
    )
  );
}

function validateLlmOverrides(
  overrides: AgentLlmOverrideValues,
): string | null {
  if (
    overrides.maxTokens !== null &&
    (!Number.isInteger(overrides.maxTokens) || overrides.maxTokens <= 0)
  ) {
    return "Maximum tokens must be a whole number greater than zero.";
  }
  if (
    overrides.temperature !== null &&
    (!Number.isFinite(overrides.temperature) ||
      overrides.temperature < 0 ||
      overrides.temperature > 2)
  ) {
    return "Temperature must be between 0 and 2.";
  }
  if (
    overrides.topK !== null &&
    (!Number.isInteger(overrides.topK) || overrides.topK <= 0)
  ) {
    return "Top K must be a whole number greater than zero.";
  }
  if (
    overrides.topP !== null &&
    (!Number.isFinite(overrides.topP) ||
      overrides.topP < 0 ||
      overrides.topP > 1)
  ) {
    return "Top P must be between 0 and 1.";
  }
  return null;
}

function buildContextKey(context: AgentFormContext): string {
  return [
    context.memberKey.toLowerCase(),
    context.organizationId,
    context.mode,
    context.agentId ?? "new",
  ].join(":");
}

export { AgentFormStore, createEmptyAgentFormValues };
