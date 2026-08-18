import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type Campaign = components["schemas"]["CampaignResponse"];
type CampaignCreate = components["schemas"]["CampaignCreateRequest"];
type CampaignUpdate = components["schemas"]["CampaignUpdateRequest"];
type CampaignPreparation = components["schemas"]["CampaignPreparationResponse"];
type CampaignAnalytics = components["schemas"]["CampaignAnalyticsResponse"];
type CampaignContact = components["schemas"]["CampaignContactResponse"];
type CampaignAgent = components["schemas"]["AgentResponseSchema"];
type CampaignTemplate = components["schemas"]["TemplateResponse"];
type CampaignEmailConfig = components["schemas"]["EmailConfigResponse"];
type OrganizationContact = components["schemas"]["ContactApiResponseSchema"];
type CampaignChannel = "email" | "voice" | "widget";

type CampaignFilterProperty = "channel" | "status";
type CampaignSortField = "name" | "progress" | "status" | "updated_at";
type CampaignSortDirection = "asc" | "desc";

interface CampaignCollectionQuery {
  direction: CampaignSortDirection;
  filters: FilterGroup<CampaignFilterProperty>;
  search: string;
  sortBy: CampaignSortField;
}

interface CampaignFormValues {
  agentId: string;
  channel: CampaignChannel | "";
  concurrencyLimit: string;
  description: string;
  emailBodyTemplate: string;
  emailConfigId: string;
  emailSubjectTemplate: string;
  initialMessageTemplateId: string;
  name: string;
  retryBackoffSeconds: string;
  retryMaxRetries: string;
  retryOn: string;
}

interface CampaignUploadContact {
  contactAddress: string;
  name?: string | null;
  variables: Record<string, unknown>;
}

export type {
  Campaign,
  CampaignAgent,
  CampaignAnalytics,
  CampaignChannel,
  CampaignCollectionQuery,
  CampaignContact,
  CampaignCreate,
  CampaignEmailConfig,
  CampaignFilterProperty,
  CampaignFormValues,
  CampaignPreparation,
  CampaignSortDirection,
  CampaignSortField,
  CampaignTemplate,
  CampaignUpdate,
  CampaignUploadContact,
  OrganizationContact,
};
