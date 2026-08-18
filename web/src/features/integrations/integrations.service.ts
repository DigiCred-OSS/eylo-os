import type { ApiClient } from "@/api/client";
import type {
  CuratedConnection,
  CuratedCredentialInput,
  CuratedExecutionMode,
  CuratedInstallation,
  CuratedInstalledTool,
  CuratedVendor,
  CuratedVendorDetail,
  IntegrationInstallDraftValues,
} from "@/features/integrations/integrations.types";

class IntegrationsServiceError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "IntegrationsServiceError";
    this.status = status;
  }
}

class IntegrationsService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listVendors(organizationId: string): Promise<CuratedVendor[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/curated-vendors", {
        params: { path: { organization_id: organizationId } },
      }),
      "Integration catalog could not be loaded.",
    );
  }

  async getVendor(
    organizationId: string,
    vendor: string,
  ): Promise<CuratedVendorDetail> {
    return requireData(
      await this.api.GET("/api/{organization_id}/curated-vendors/{vendor}", {
        params: { path: { organization_id: organizationId, vendor } },
      }),
      "This integration could not be loaded.",
    );
  }

  async listInstallations(
    organizationId: string,
  ): Promise<CuratedInstallation[]> {
    return requireData(
      await this.api.GET("/api/{organization_id}/curated-integrations", {
        params: { path: { organization_id: organizationId } },
      }),
    );
  }

  async listConnections(organizationId: string): Promise<CuratedConnection[]> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/aggregate/curated-connections",
        {
          params: { path: { organization_id: organizationId } },
        },
      ),
    );
  }

  async deleteConnection(
    organizationId: string,
    connectionId: string,
  ): Promise<void> {
    requireSuccess(
      await this.api.DELETE(
        "/api/{organization_id}/curated-connections/{connection_id}",
        {
          params: {
            path: {
              organization_id: organizationId,
              connection_id: connectionId,
            },
          },
        },
      ),
      "Connection could not be deleted.",
    );
  }

  async listTools(
    organizationId: string,
    vendor: string,
  ): Promise<CuratedInstalledTool[]> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/curated-vendors/{vendor}/tools",
        { params: { path: { organization_id: organizationId, vendor } } },
      ),
    );
  }

  async install(
    organizationId: string,
    vendor: string,
    values: IntegrationInstallDraftValues,
    oauthClientSecret: string,
  ): Promise<CuratedInstallation> {
    if (values.authKind === "") {
      throw new Error("Choose an authorization method.");
    }
    return requireData(
      await this.api.POST(
        "/api/{organization_id}/curated-vendors/{vendor}/install",
        {
          params: { path: { organization_id: organizationId, vendor } },
          body: {
            authKind: values.authKind,
            instanceUrl: values.instanceUrl.trim() || null,
            oauthClientId: values.oauthClientId.trim() || null,
            oauthClientSecret: oauthClientSecret || null,
            oauthTenant: values.oauthTenant.trim() || null,
          },
        },
      ),
    );
  }

  async setExecutionMode(
    organizationId: string,
    vendor: string,
    toolName: string,
    executionMode: CuratedExecutionMode,
  ): Promise<CuratedInstalledTool> {
    return requireData(
      await this.api.PUT(
        "/api/{organization_id}/curated-vendors/{vendor}/tools/{tool_name}/execution-mode",
        {
          params: {
            path: {
              organization_id: organizationId,
              vendor,
              tool_name: toolName,
            },
          },
          body: { executionMode },
        },
      ),
    );
  }

  async connect(
    organizationId: string,
    vendor: string,
    credentials: CuratedCredentialInput,
  ): Promise<void> {
    requireData(
      await this.api.POST(
        "/api/{organization_id}/curated-vendors/{vendor}/connect",
        {
          params: { path: { organization_id: organizationId, vendor } },
          body: { ...credentials, contactId: null },
        },
      ),
    );
  }

  async beginAuthorization(
    organizationId: string,
    vendor: string,
  ): Promise<{ authorizationUrl: string; callbackOrigin: string }> {
    const result = requireData(
      await this.api.POST(
        "/api/{organization_id}/curated-vendors/{vendor}/authorize",
        {
          params: { path: { organization_id: organizationId, vendor } },
          body: { contactId: null },
        },
      ),
    );
    return {
      authorizationUrl: result.authorizationUrl,
      callbackOrigin: result.callbackOrigin,
    };
  }
}

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

function requireData<Data>(
  result: ApiResult<Data>,
  fallback = "The integration request failed. Review the values and try again.",
): Data {
  if (result.response.ok && result.data !== undefined) return result.data;
  throw new IntegrationsServiceError(
    errorMessage(result.error, fallback),
    result.response.status,
  );
}

function requireSuccess(result: ApiResult<unknown>, fallback: string): void {
  if (result.response.ok) return;
  throw new IntegrationsServiceError(
    errorMessage(result.error, fallback),
    result.response.status,
  );
}

function errorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim() !== "") return detail;
  }
  return fallback;
}

export { IntegrationsService, IntegrationsServiceError };
