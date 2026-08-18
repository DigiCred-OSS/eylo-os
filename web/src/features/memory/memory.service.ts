import type { ApiClient } from "@/api/client";
import type {
  MemoryDetail,
  MemoryListRequest,
  MemoryReindexJob,
  MemoryReindexStatus,
} from "@/features/memory/memory.types";
import type { components } from "@/api/generated/schema";

type MemoryPage = components["schemas"]["MemoryListRead"];

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class MemoryServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "MemoryServiceError";
    this.status = status;
  }
}

class MemoryService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listMemories(
    organizationId: string,
    request: MemoryListRequest,
    signal?: AbortSignal,
  ): Promise<MemoryPage> {
    return requireData(
      await this.api.GET("/api/{organization_id}/memories", {
        params: {
          path: { organization_id: organizationId },
          query: {
            direction: request.direction,
            integrity:
              request.integrities.length > 0 ? request.integrities : undefined,
            level: request.levels.length > 0 ? request.levels : undefined,
            limit: 100,
            offset: request.offset,
            query: request.query === "" ? undefined : request.query,
            recalled: request.recalled ?? undefined,
            sort: request.sort,
            status: request.statuses.length > 0 ? request.statuses : undefined,
          },
        },
        signal,
      }),
      "Memories could not be loaded.",
    );
  }

  async getMemory(
    organizationId: string,
    memoryId: string,
    signal?: AbortSignal,
  ): Promise<MemoryDetail> {
    return requireData(
      await this.api.GET("/api/{organization_id}/memories/{memory_id}", {
        params: {
          path: {
            memory_id: memoryId,
            organization_id: organizationId,
          },
        },
        signal,
      }),
      "This memory could not be loaded.",
    );
  }

  async getReindexStatus(
    configId: string,
    signal?: AbortSignal,
  ): Promise<MemoryReindexStatus> {
    return requireData(
      await this.api.GET("/api/memory-configs/{config_id}/reindex", {
        params: { path: { config_id: configId } },
        signal,
      }),
      "Memory index status could not be loaded.",
    );
  }

  async reindex(configId: string): Promise<MemoryReindexJob> {
    return requireData(
      await this.api.POST("/api/memory-configs/{config_id}/reindex", {
        params: { path: { config_id: configId } },
      }),
      "Memory reindex could not be started.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) {
    return result.data;
  }
  throw new MemoryServiceError(
    readDetail(result.error) ?? fallback,
    result.response.status,
  );
}

function readDetail(error: unknown): string | null {
  if (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    typeof error.detail === "string"
  ) {
    return error.detail;
  }
  return null;
}

export { MemoryService, MemoryServiceError };
export type { MemoryPage };
