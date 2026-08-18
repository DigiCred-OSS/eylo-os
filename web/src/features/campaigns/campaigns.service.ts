import type { ApiClient } from "@/api/client";
import type {
  Campaign,
  CampaignAgent,
  CampaignAnalytics,
  CampaignContact,
  CampaignCreate,
  CampaignEmailConfig,
  CampaignPreparation,
  CampaignTemplate,
  CampaignUpdate,
  CampaignUploadContact,
  OrganizationContact,
} from "@/features/campaigns/campaigns.types";

interface ApiResult<Data> {
  data?: Data;
  error?: unknown;
  response: Response;
}

class CampaignsServiceError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "CampaignsServiceError";
    this.status = status;
  }
}

class CampaignsService {
  private readonly api: ApiClient;
  constructor(api: ApiClient) {
    this.api = api;
  }

  async list(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<Campaign[]> {
    const page = requireData(
      await this.api.GET("/api/{organization_id}/campaigns", {
        params: {
          path: { organization_id: organizationId },
          query: { limit: 100, page: 1 },
        },
        signal,
      }),
      "Campaigns could not be loaded.",
    );
    return page.data;
  }

  async get(
    organizationId: string,
    campaignId: string,
    signal?: AbortSignal,
  ): Promise<Campaign> {
    return requireData(
      await this.api.GET("/api/{organization_id}/campaigns/{campaign_id}", {
        params: {
          path: { campaign_id: campaignId, organization_id: organizationId },
        },
        signal,
      }),
      "This campaign could not be loaded.",
    );
  }

  async create(
    organizationId: string,
    input: CampaignCreate,
  ): Promise<Campaign> {
    return requireData(
      await this.api.POST("/api/{organization_id}/campaigns", {
        params: { path: { organization_id: organizationId } },
        body: input,
      }),
      "The campaign could not be created.",
    );
  }

  async update(
    organizationId: string,
    campaignId: string,
    input: CampaignUpdate,
  ): Promise<Campaign> {
    return requireData(
      await this.api.PUT("/api/{organization_id}/campaigns/{campaign_id}", {
        params: {
          path: { campaign_id: campaignId, organization_id: organizationId },
        },
        body: input,
      }),
      "The campaign could not be updated.",
    );
  }

  async remove(organizationId: string, campaignId: string): Promise<void> {
    const result = await this.api.DELETE(
      "/api/{organization_id}/campaigns/{campaign_id}",
      {
        params: {
          path: { campaign_id: campaignId, organization_id: organizationId },
        },
      },
    );
    requireNoContent(result, "The campaign could not be deleted.");
  }

  async preparation(
    organizationId: string,
    campaignId: string,
    signal?: AbortSignal,
  ): Promise<CampaignPreparation> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/campaigns/{campaign_id}/preparation",
        {
          params: {
            path: { campaign_id: campaignId, organization_id: organizationId },
          },
          signal,
        },
      ),
      "Campaign preparation could not be loaded.",
    );
  }

  async transition(
    organizationId: string,
    campaignId: string,
    action: "cancel" | "pause" | "start",
  ): Promise<Campaign> {
    const path =
      action === "start"
        ? ("/api/{organization_id}/campaigns/{campaign_id}/start" as const)
        : action === "pause"
          ? ("/api/{organization_id}/campaigns/{campaign_id}/pause" as const)
          : ("/api/{organization_id}/campaigns/{campaign_id}/cancel" as const);
    return requireData(
      await this.api.POST(path, {
        params: {
          path: { campaign_id: campaignId, organization_id: organizationId },
        },
      }),
      `The campaign could not ${action}.`,
    );
  }

  async revoke(
    organizationId: string,
    campaign: Campaign,
    reason: string,
  ): Promise<void> {
    const result = await this.api.POST(
      "/api/{organization_id}/campaigns/{campaign_id}/revisions/{revision}/revoke",
      {
        params: {
          path: {
            campaign_id: campaign.id,
            organization_id: organizationId,
            revision: campaign.publishedRevision,
          },
        },
        body: { reason },
      },
    );
    requireNoContent(result, "The campaign revision could not be revoked.");
  }

  async contacts(
    organizationId: string,
    campaignId: string,
    signal?: AbortSignal,
  ): Promise<CampaignContact[]> {
    const page = requireData(
      await this.api.GET(
        "/api/{organization_id}/campaigns/{campaign_id}/contacts",
        {
          params: {
            path: { campaign_id: campaignId, organization_id: organizationId },
            query: { limit: 100, page: 1 },
          },
          signal,
        },
      ),
      "Campaign recipients could not be loaded.",
    );
    return page.data;
  }

  async analytics(
    organizationId: string,
    campaignId: string,
    signal?: AbortSignal,
  ): Promise<CampaignAnalytics> {
    return requireData(
      await this.api.GET(
        "/api/{organization_id}/campaigns/{campaign_id}/analytics",
        {
          params: {
            path: { campaign_id: campaignId, organization_id: organizationId },
          },
          signal,
        },
      ),
      "Campaign analytics could not be loaded.",
    );
  }

  async selectContacts(
    organizationId: string,
    campaignId: string,
    contactIds: string[],
  ): Promise<void> {
    const result = await this.api.POST(
      "/api/{organization_id}/campaigns/{campaign_id}/contacts/select",
      {
        params: {
          path: { campaign_id: campaignId, organization_id: organizationId },
        },
        body: { contactIds },
      },
    );
    requireData(result, "Contacts could not be added to the campaign.");
  }

  async uploadContacts(
    organizationId: string,
    campaignId: string,
    contacts: CampaignUploadContact[],
  ): Promise<void> {
    const result = await this.api.POST(
      "/api/{organization_id}/campaigns/{campaign_id}/contacts",
      {
        params: {
          path: { campaign_id: campaignId, organization_id: organizationId },
        },
        body: { contacts },
      },
    );
    requireData(result, "Addresses could not be added to the campaign.");
  }

  async agents(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<CampaignAgent[]> {
    const page = requireData(
      await this.api.GET("/api/{organization_id}/agents", {
        params: {
          path: { organization_id: organizationId },
          query: {
            limit: 100,
            page: 1,
            sort_by: "name",
            sort_direction: "asc",
          },
        },
        signal,
      }),
      "Agent references could not be loaded.",
    );
    return page.data.filter(
      (agent) =>
        agent.publishedRevision !== null &&
        agent.publishedRevision !== undefined,
    );
  }

  async templates(signal?: AbortSignal): Promise<CampaignTemplate[]> {
    const templates = requireData(
      await this.api.GET("/api/templates", { signal }),
      "Campaign templates could not be loaded.",
    );
    return templates.filter(
      (template) =>
        template.kind === "campaign_message" &&
        template.published_revision !== null &&
        template.lifecycle === "published",
    );
  }

  async emailConfigs(signal?: AbortSignal): Promise<CampaignEmailConfig[]> {
    const configs = requireData(
      await this.api.GET("/api/email-configs", { signal }),
      "Email configurations could not be loaded.",
    );
    return configs.filter((config) => config.ready);
  }

  async organizationContacts(
    organizationId: string,
    signal?: AbortSignal,
  ): Promise<OrganizationContact[]> {
    const page = requireData(
      await this.api.GET("/api/{organization_id}/contacts", {
        params: {
          path: { organization_id: organizationId },
          query: {
            lifecycle: ["active"],
            limit: 100,
            page: 1,
            sort_by: "name",
            sort_direction: "asc",
          },
        },
        signal,
      }),
      "Organization contacts could not be loaded.",
    );
    return page.data;
  }
}

function requireData<Data>(result: ApiResult<Data>, fallback: string): Data {
  if (result.data !== undefined) return result.data;
  throw new CampaignsServiceError(
    readDetail(result.error) ?? fallback,
    result.response.status,
  );
}

function requireNoContent(result: ApiResult<unknown>, fallback: string): void {
  if (result.response.ok) return;
  throw new CampaignsServiceError(
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
  )
    return error.detail;
  return null;
}

export { CampaignsService, CampaignsServiceError };
