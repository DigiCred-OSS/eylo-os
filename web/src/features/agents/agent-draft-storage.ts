import {
  AGENT_KINDS,
  type AgentFormMode,
  type AgentFormValues,
  type AgentLlmModel,
  type AgentLlmOverrideValues,
} from "@/features/agents/agents.types";

interface AgentDraftContext {
  agentId: string | null;
  memberKey: string;
  mode: AgentFormMode;
  organizationId: string;
}

interface StoredAgentDraft {
  baseDraftVersion: number | null;
  savedAt: string;
  values: AgentFormValues;
  version: 1;
}

class AgentDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: AgentDraftContext): void {
    try {
      this.storage.removeItem(buildDraftKey(context));
    } catch {
      // Draft cleanup must not change the Agent API mutation outcome.
    }
  }

  read(context: AgentDraftContext): StoredAgentDraft | null {
    const key = buildDraftKey(context);
    try {
      const serialized = this.storage.getItem(key);
      if (serialized === null) {
        return null;
      }
      const parsed: unknown = JSON.parse(serialized);
      const draft = parseStoredDraft(parsed);

      if (draft === null) {
        this.clear(context);
      }

      return draft;
    } catch {
      this.clear(context);
      return null;
    }
  }

  write(context: AgentDraftContext, draft: StoredAgentDraft): boolean {
    try {
      this.storage.setItem(buildDraftKey(context), JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }
}

function buildDraftKey(context: AgentDraftContext): string {
  const recordKey = context.agentId ?? "new";
  return [
    "eylo.agent-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.mode,
    recordKey,
  ].join(":");
}

function parseStoredDraft(value: unknown): StoredAgentDraft | null {
  if (!isRecord(value) || value.version !== 1) {
    return null;
  }

  const values = parseFormValues(value.values);
  const savedAt = parseDate(value.savedAt);
  const baseDraftVersion = parseDraftVersion(value.baseDraftVersion);

  if (values === null || savedAt === null || baseDraftVersion === undefined) {
    return null;
  }

  return {
    baseDraftVersion,
    savedAt,
    values,
    version: 1,
  };
}

function parseFormValues(value: unknown): AgentFormValues | null {
  if (!isRecord(value)) {
    return null;
  }

  const name = parseString(value.name, 100);
  const description = parseString(value.description, 20_000);
  const kind = AGENT_KINDS.includes(value.kind as (typeof AGENT_KINDS)[number])
    ? (value.kind as AgentFormValues["kind"])
    : null;
  const llmOverrides = parseLlmOverrides(value.llmOverrides);
  const allowFileUploads =
    value.allowFileUploads === undefined
      ? false
      : parseBoolean(value.allowFileUploads);

  if (
    name === null ||
    description === null ||
    kind === null ||
    llmOverrides === null ||
    allowFileUploads === null
  ) {
    return null;
  }

  const references = {
    emailProviderConfigId: parseNullableString(value.emailProviderConfigId),
    fileUploadEmbeddingProviderConfigId: parseNullableString(
      value.fileUploadEmbeddingProviderConfigId,
    ),
    instructionTemplateId: parseNullableString(value.instructionTemplateId),
    llmProviderConfigId: parseNullableString(value.llmProviderConfigId),
    memoryProviderConfigId: parseNullableString(value.memoryProviderConfigId),
    rerankingProviderConfigId: parseNullableString(
      value.rerankingProviderConfigId,
    ),
    voiceConfigId: parseNullableString(value.voiceConfigId),
    webrtcProviderConfigId: parseNullableString(value.webrtcProviderConfigId),
  };

  if (Object.values(references).some((reference) => reference === undefined)) {
    return null;
  }

  return {
    allowFileUploads,
    description,
    emailProviderConfigId: references.emailProviderConfigId ?? null,
    fileUploadEmbeddingProviderConfigId:
      references.fileUploadEmbeddingProviderConfigId ?? null,
    instructionTemplateId: references.instructionTemplateId ?? null,
    kind,
    llmOverrides,
    llmProviderConfigId: references.llmProviderConfigId ?? null,
    memoryProviderConfigId: references.memoryProviderConfigId ?? null,
    name,
    rerankingProviderConfigId: references.rerankingProviderConfigId ?? null,
    voiceConfigId: references.voiceConfigId ?? null,
    webrtcProviderConfigId: references.webrtcProviderConfigId ?? null,
  };
}

function parseLlmOverrides(value: unknown): AgentLlmOverrideValues | null {
  if (value === undefined) {
    return createEmptyLlmOverrides();
  }
  if (!isRecord(value)) {
    return null;
  }

  const model = parseLlmModel(value.model);
  const maxTokens = parseNullableNumber(value.maxTokens);
  const temperature = parseNullableNumber(value.temperature);
  const topK = parseNullableNumber(value.topK);
  const topP = parseNullableNumber(value.topP);
  const stopSequences = parseStringList(value.stopSequences);

  if (
    model === undefined ||
    maxTokens === undefined ||
    temperature === undefined ||
    topK === undefined ||
    topP === undefined ||
    stopSequences === null
  ) {
    return null;
  }

  return { maxTokens, model, stopSequences, temperature, topK, topP };
}

function parseBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
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

function parseLlmModel(value: unknown): AgentLlmModel | null | undefined {
  if (value === null || value === undefined) {
    return null;
  }
  return typeof value === "string" && value.length <= 256
    ? (value as AgentLlmModel)
    : undefined;
}

function parseNullableNumber(value: unknown): number | null | undefined {
  if (value === null || value === undefined) {
    return null;
  }
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function parseStringList(value: unknown): string[] | null {
  if (value === null || value === undefined) {
    return [];
  }
  return Array.isArray(value) &&
    value.length <= 100 &&
    value.every((item) => typeof item === "string" && item.length <= 1_000)
    ? value
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseString(value: unknown, maxLength: number): string | null {
  return typeof value === "string" && value.length <= maxLength ? value : null;
}

function parseNullableString(value: unknown): string | null | undefined {
  if (value === null) {
    return null;
  }

  return typeof value === "string" && value.length <= 100 ? value : undefined;
}

function parseDate(value: unknown): string | null {
  if (typeof value !== "string" || Number.isNaN(new Date(value).getTime())) {
    return null;
  }

  return value;
}

function parseDraftVersion(value: unknown): number | null | undefined {
  if (value === null) {
    return null;
  }

  return Number.isSafeInteger(value) && Number(value) > 0
    ? Number(value)
    : undefined;
}

export { AgentDraftStorage };
export type { AgentDraftContext, StoredAgentDraft };
