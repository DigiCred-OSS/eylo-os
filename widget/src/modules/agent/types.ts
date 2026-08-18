export type TAgentStatus = "DRAFT" | "ACTIVE" | "INACTIVE" | "ARCHIVED";

/**
 * Integration summary for agent tools display
 */
export type TIntegrationSummary = {
  id: string;
  source?: "curated";
  vendor?: string;
  name: string;
  slug: string;
  displayName?: string;
  description?: string;
  iconUrl?: string;
  authKind: string;
  connectionKind?: "ORGANIZATION" | "CONTACT";
  hasActiveConnection: boolean;
};

/**
 * Agent tool summary
 */
export type TAgentTool = {
  id: string;
  name: string;
  slug: string;
  displayName: string;
  description: string;
  kind: string;
};

/**
 * Agent tools grouped by integration
 */
export type TAgentToolsByIntegration = {
  integration: TIntegrationSummary | null;
  tools: TAgentTool[];
};

/**
 * Core agent type
 */
export type TAgent = {
  id: string;
  name: string;
  status: TAgentStatus;
  externalId?: string;
  organizationId?: string;
  description?: string;
  // Optional fields for enriched agent data
  integrations?: TAgentToolsByIntegration[];
};
