import type { ApiClient } from "@/api/client";
import type {
  CorpusImport,
  CorpusImportInput,
  EmbeddingConfig,
  IngestionInput,
  IngestionJob,
  KnowledgeAgentOption,
  Knowledgebase,
  KnowledgebaseCreateInput,
  KnowledgebaseUpdateInput,
  KnowledgeReindexJob,
  KnowledgeReindexStatus,
  StorageConfig,
} from "@/features/knowledge/knowledge.types";

const REQUEST_ERROR_MESSAGE =
  "The Knowledge request failed. Review the values and try again.";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class KnowledgeServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "KnowledgeServiceError";
    this.status = status;
  }
}

class KnowledgeService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listKnowledgebases(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<Knowledgebase[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/knowledgebases", {
        params: { path: { organization_id: organizationId } },
        signal,
      }),
      "Knowledgebases could not be loaded.",
    );
  }

  async getKnowledgebase(
    organizationId: string,
    knowledgebaseId: string,
    signal?: AbortSignal,
  ): Promise<Knowledgebase> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          signal,
        },
      ),
      "This knowledgebase could not be loaded.",
    );
  }

  async createKnowledgebase(
    organizationId: string,
    input: KnowledgebaseCreateInput,
  ): Promise<Knowledgebase> {
    return requireData(
      await this.api.POST("/api/{organization_id}/knowledgebases", {
        params: { path: { organization_id: organizationId } },
        body: input,
      }),
    );
  }

  async updateKnowledgebase(
    organizationId: string,
    knowledgebaseId: string,
    input: KnowledgebaseUpdateInput,
  ): Promise<Knowledgebase> {
    return requireData(
      await this.api.PATCH(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          body: input,
        },
      ),
    );
  }

  async deleteKnowledgebase(
    organizationId: string,
    knowledgebaseId: string,
  ): Promise<void> {
    requireSuccess(
      await this.api.DELETE(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
        },
      ),
    );
  }

  async getReindexStatus(
    organizationId: string,
    knowledgebaseId: string,
    signal?: AbortSignal,
  ): Promise<KnowledgeReindexStatus> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/reindex",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          signal,
        },
      ),
      "Embedding index status could not be loaded.",
    );
  }

  async reindexKnowledgebase(
    organizationId: string,
    knowledgebaseId: string,
    embeddingProviderConfigId: string,
  ): Promise<KnowledgeReindexJob> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/reindex",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          body: {
            embedding_provider_config_id: embeddingProviderConfigId,
          },
        },
      ),
      "Reindex could not be started.",
    );
  }

  async listEmbeddingConfigs(): Promise<EmbeddingConfig[]> {
    return requireData(
      await this.api.GET("/api/embedding-configs"),
      "Embedding provider configurations could not be loaded.",
    );
  }

  async listStorageConfigs(): Promise<StorageConfig[]> {
    return requireData(
      await this.api.GET("/api/storage-configs"),
      "Storage provider configurations could not be loaded.",
    );
  }

  async listAgentOptions(
    organizationId: string,
  ): Promise<KnowledgeAgentOption[]> {
    const items: KnowledgeAgentOption[] = [];
    let page = 1;

    for (;;) {
      const result = await this.api.GET("/api/{organization_id}/agents", {
        params: {
          path: { organization_id: organizationId },
          query: {
            limit: 100,
            page,
            sort_by: "name",
            sort_direction: "asc",
          },
        },
      });
      const data = requireData(
        result,
        "Agents could not be loaded for scope selection.",
      );
      items.push(
        ...data.data.map((agent) => ({
          id: agent.id,
          kind: agent.kind,
          label: agent.name,
          lifecycle: agent.lifecycle,
        })),
      );
      if (data.hasMore !== true) {
        return items;
      }
      page += 1;
    }
  }

  async listIngestions(
    organizationId: string,
    knowledgebaseId: string,
    signal?: AbortSignal,
  ): Promise<IngestionJob[]> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          signal,
        },
      ),
      "Ingestion jobs could not be loaded.",
    );
  }

  async submitIngestion(
    organizationId: string,
    knowledgebaseId: string,
    input: IngestionInput,
  ): Promise<IngestionJob> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          body: input,
        },
      ),
    );
  }

  async cancelIngestion(
    organizationId: string,
    knowledgebaseId: string,
    jobId: string,
  ): Promise<IngestionJob> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/{job_id}/cancel",
        {
          params: {
            path: {
              job_id: jobId,
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
        },
      ),
    );
  }

  async listCorpusImports(
    organizationId: string,
    knowledgebaseId: string,
    signal?: AbortSignal,
  ): Promise<CorpusImport[]> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/corpus",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          signal,
        },
      ),
      "Corpus imports could not be loaded.",
    );
  }

  async startCorpusImport(
    organizationId: string,
    knowledgebaseId: string,
    input: CorpusImportInput,
  ): Promise<CorpusImport> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/corpus",
        {
          params: {
            path: {
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
          body: input,
        },
      ),
    );
  }

  async cancelCorpusImport(
    organizationId: string,
    knowledgebaseId: string,
    importId: string,
  ): Promise<CorpusImport> {
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/knowledgebases/{knowledgebase_id}/ingestions/corpus/{import_id}/cancel",
        {
          params: {
            path: {
              import_id: importId,
              knowledgebase_id: knowledgebaseId,
              organization_id: organizationId,
            },
          },
        },
      ),
    );
  }
}

function requireData<Data>(
  result: ApiResult<Data>,
  fallback = REQUEST_ERROR_MESSAGE,
): Data {
  if (!result.response.ok || result.data === undefined) {
    throw new KnowledgeServiceError(
      getSafeErrorMessage(result.error, fallback),
      result.response.status,
    );
  }
  return result.data;
}

function requireSuccess(
  result: ApiResult<unknown>,
  fallback = REQUEST_ERROR_MESSAGE,
): void {
  if (!result.response.ok) {
    throw new KnowledgeServiceError(
      getSafeErrorMessage(result.error, fallback),
      result.response.status,
    );
  }
}

function getSafeErrorMessage(error: unknown, fallback: string): string {
  if (typeof error !== "object" || error === null || !("detail" in error)) {
    return fallback;
  }

  const detail = error.detail;
  if (typeof detail === "string" && detail.trim() !== "") {
    return detail.slice(0, 500);
  }
  if (!Array.isArray(detail)) {
    return fallback;
  }

  const messages = detail.flatMap((item) => {
    if (
      typeof item !== "object" ||
      item === null ||
      !("msg" in item) ||
      typeof item.msg !== "string"
    ) {
      return [];
    }
    return [item.msg];
  });
  return messages.length > 0 ? messages.join(" ").slice(0, 500) : fallback;
}

export { KnowledgeService, KnowledgeServiceError };
