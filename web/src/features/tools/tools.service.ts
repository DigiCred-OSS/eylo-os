import type { ApiClient } from "@/api/client";
import type {
  ToolCapability,
  ToolRecord,
  ToolSource,
} from "@/features/tools/tools.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class ToolsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ToolsServiceError";
    this.status = status;
  }
}

class ToolsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async list(
    organizationId: string,
    source: ToolSource,
    capability: ToolCapability,
    signal?: AbortSignal,
  ): Promise<ToolRecord[]> {
    if (source === "system") {
      return requireData(
        await this.api.GET("/api/{organization_id}/tools/system-catalog", {
          params: { path: { organization_id: organizationId } },
          signal,
        }),
        "System tools could not be loaded.",
      ).items;
    }
    if (source === "provider") {
      return requireData(
        await this.api.GET("/api/{organization_id}/tools/provider-catalog", {
          params: {
            path: { organization_id: organizationId },
            query: { capability },
          },
          signal,
        }),
        "Provider tools could not be loaded.",
      ).items;
    }
    return requireData(
      await this.api.GET("/api/{organization_id}/tools", {
        params: { path: { organization_id: organizationId } },
        signal,
      }),
      "Managed tools could not be loaded.",
    ).items;
  }

  async get(
    organizationId: string,
    toolId: string,
    signal?: AbortSignal,
  ): Promise<ToolRecord> {
    return requireData(
      await this.api.GET("/api/{organization_id}/tools/{tool_id}", {
        params: {
          path: { organization_id: organizationId, tool_id: toolId },
        },
        signal,
      }),
      "This tool could not be loaded.",
    );
  }

  async publish(organizationId: string, tool: ToolRecord): Promise<void> {
    requireData(
      await this.api.POST("/api/{organization_id}/tools/{tool_id}/publish", {
        params: {
          path: { organization_id: organizationId, tool_id: tool.id },
        },
        body: { expectedDraftVersion: tool.draftVersion },
      }),
      "The tool could not be published.",
    );
  }

  async withdraw(organizationId: string, toolId: string): Promise<ToolRecord> {
    return requireData(
      await this.api.POST("/api/{organization_id}/tools/{tool_id}/withdraw", {
        params: {
          path: { organization_id: organizationId, tool_id: toolId },
        },
      }),
      "The tool could not be withdrawn.",
    );
  }

  async revoke(
    organizationId: string,
    tool: ToolRecord,
    reason: string,
  ): Promise<void> {
    if (
      tool.publishedRevision === null ||
      tool.publishedRevision === undefined
    ) {
      throw new ToolsServiceError("This tool has no published revision.", 409);
    }
    requireData(
      await this.api.POST(
        "/api/{organization_id}/tools/{tool_id}/revisions/{revision}/revoke",
        {
          params: {
            path: {
              organization_id: organizationId,
              revision: tool.publishedRevision,
              tool_id: tool.id,
            },
          },
          body: { reason },
        },
      ),
      "The tool revision could not be revoked.",
    );
  }

  async delete(organizationId: string, toolId: string): Promise<void> {
    requireData(
      await this.api.DELETE("/api/{organization_id}/tools/{tool_id}", {
        params: {
          path: { organization_id: organizationId, tool_id: toolId },
        },
      }),
      "The tool could not be deleted.",
    );
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) {
    return result.data;
  }
  throw new ToolsServiceError(
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

export { ToolsService, ToolsServiceError };
