import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import type {
  ProviderReferenceField,
  ProviderReferenceOption,
} from "@/features/providers/providers.types";

const PROVIDER_REFERENCE_FIELDS: readonly ProviderReferenceField[] = [
  "llmProviderConfigId",
  "emailProviderConfigId",
  "fileUploadEmbeddingProviderConfigId",
  "webrtcProviderConfigId",
  "rerankingProviderConfigId",
  "memoryProviderConfigId",
  "sttProviderConfigId",
  "ttsProviderConfigId",
  "realtimeProviderConfigId",
  "storageProviderConfigId",
];

type ReferenceOptions = Record<
  ProviderReferenceField,
  ProviderReferenceOption[]
>;

interface ProviderConfigProjection {
  id: string;
  name: string;
  provider: string;
  ready: boolean;
  revision: number;
}

class ProviderReferencesStore {
  errorFields = new Set<ProviderReferenceField>();
  loadingFields = new Set<ProviderReferenceField>();
  options: ReferenceOptions = createEmptyOptions();

  private readonly api: ApiClient;
  private loadedFields = new Set<ProviderReferenceField>();
  private organizationId: string | null = null;

  constructor(api: ApiClient) {
    this.api = api;
    makeAutoObservable<this, "api" | "loadedFields" | "organizationId">(
      this,
      {
        api: false,
        loadedFields: false,
        organizationId: false,
      },
      { autoBind: true },
    );
  }

  getOption(
    field: ProviderReferenceField,
    id: string | null,
  ): ProviderReferenceOption | null {
    if (id === null) {
      return null;
    }
    return this.options[field].find((option) => option.id === id) ?? null;
  }

  async load(
    field: ProviderReferenceField,
    organizationId: string,
    force = false,
  ): Promise<void> {
    this.prepareOrganization(organizationId);
    if (
      this.loadingFields.has(field) ||
      (!force && this.loadedFields.has(field))
    ) {
      return;
    }

    this.loadingFields.add(field);
    this.errorFields.delete(field);
    try {
      const options = await this.fetchOptions(field);
      if (this.organizationId !== organizationId) {
        return;
      }
      runInAction(() => {
        this.options[field] = options;
        this.loadedFields.add(field);
      });
    } catch {
      if (this.organizationId === organizationId) {
        runInAction(() => {
          this.errorFields.add(field);
        });
      }
    } finally {
      if (this.organizationId === organizationId) {
        runInAction(() => {
          this.loadingFields.delete(field);
        });
      }
    }
  }

  async loadAll(
    organizationId: string,
    fields: readonly ProviderReferenceField[] = PROVIDER_REFERENCE_FIELDS,
  ): Promise<void> {
    await Promise.all(fields.map((field) => this.load(field, organizationId)));
  }

  private async fetchOptions(
    field: ProviderReferenceField,
  ): Promise<ProviderReferenceOption[]> {
    switch (field) {
      case "llmProviderConfigId":
        return this.fetch("/api/llm-configs");
      case "emailProviderConfigId":
        return this.fetch("/api/email-configs");
      case "fileUploadEmbeddingProviderConfigId":
        return this.fetch("/api/embedding-configs");
      case "webrtcProviderConfigId":
        return this.fetch("/api/webrtc-configs");
      case "rerankingProviderConfigId":
        return this.fetch("/api/reranking-configs");
      case "memoryProviderConfigId":
        return this.fetch("/api/memory-configs");
      case "sttProviderConfigId":
        return this.fetch("/api/stt-configs");
      case "ttsProviderConfigId":
        return this.fetch("/api/tts-configs");
      case "realtimeProviderConfigId":
        return this.fetch("/api/realtime-configs");
      case "storageProviderConfigId":
        return this.fetch("/api/storage-configs");
    }
  }

  private async fetch(
    path:
      | "/api/llm-configs"
      | "/api/email-configs"
      | "/api/embedding-configs"
      | "/api/webrtc-configs"
      | "/api/reranking-configs"
      | "/api/memory-configs"
      | "/api/stt-configs"
      | "/api/tts-configs"
      | "/api/realtime-configs"
      | "/api/storage-configs",
  ): Promise<ProviderReferenceOption[]> {
    const { data, response } = await this.api.GET(path);
    assertSuccessfulResponse(response, data);
    return mapProviderOptions(data);
  }

  private prepareOrganization(organizationId: string): void {
    if (this.organizationId === organizationId) {
      return;
    }
    this.organizationId = organizationId;
    this.options = createEmptyOptions();
    this.errorFields.clear();
    this.loadingFields.clear();
    this.loadedFields.clear();
  }
}

function mapProviderOptions(
  configs: readonly ProviderConfigProjection[],
): ProviderReferenceOption[] {
  return configs.map((config) => ({
    description: `${config.provider} · revision ${config.revision}`,
    id: config.id,
    isSelectable: config.ready,
    label: config.name,
    provider: config.provider,
    status: config.ready ? "Ready" : "Not ready",
  }));
}

function assertSuccessfulResponse<T>(
  response: Response,
  data: T | undefined,
): asserts data is T {
  if (!response.ok || data === undefined) {
    throw new Error("Provider reference collection request failed");
  }
}

function createEmptyOptions(): ReferenceOptions {
  return {
    emailProviderConfigId: [],
    fileUploadEmbeddingProviderConfigId: [],
    llmProviderConfigId: [],
    memoryProviderConfigId: [],
    realtimeProviderConfigId: [],
    rerankingProviderConfigId: [],
    storageProviderConfigId: [],
    sttProviderConfigId: [],
    ttsProviderConfigId: [],
    webrtcProviderConfigId: [],
  };
}

export { PROVIDER_REFERENCE_FIELDS, ProviderReferencesStore };
