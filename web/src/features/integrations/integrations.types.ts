import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type CuratedVendor = components["schemas"]["CuratedVendorSummarySchema"];
type CuratedVendorDetail = components["schemas"]["CuratedVendorDetailSchema"];
type CuratedInstallation = components["schemas"]["InstallationSchema"];
type CuratedConnection = components["schemas"]["ConnectionAggregateSchema"];
type CuratedInstalledTool = components["schemas"]["InstalledToolSchema"];
type CuratedAuthKind = components["schemas"]["VendorAuthKind"];
type CuratedExecutionMode =
  components["schemas"]["eylo__modules__integrations_v2__domain__enums__ToolExecutionMode"];

interface IntegrationInstallDraftValues {
  authKind: CuratedAuthKind | "";
  instanceUrl: string;
  oauthClientId: string;
  oauthTenant: string;
}

interface IntegrationDraftContext {
  memberKey: string;
  organizationId: string;
  vendor: string;
}

interface StoredIntegrationDraft {
  savedAt: string;
  values: IntegrationInstallDraftValues;
  version: 1;
}

interface CuratedCredentialInput {
  apiKey?: string;
  username?: string;
  password?: string;
}

interface IntegrationCatalogQuery {
  auth: CuratedAuthKind | "all";
  category: string;
  installed: "all" | "configured" | "available";
  search: string;
  sort: "name" | "tools";
}

const CURATED_AUTH_KINDS = [
  "no_auth",
  "api_key",
  "basic",
  "oauth2",
] as const satisfies readonly CuratedAuthKind[];
const CURATED_CONNECTION_KINDS = ["ORGANIZATION", "CONTACT"] as const;
const CURATED_CONNECTION_STATUSES = [
  "INITIATED",
  "ACTIVE",
  "INACTIVE",
  "FAILED",
  "REVOKED",
] as const;
const CONFIGURED_CONNECTION_STATES = [
  "active",
  "attention",
  "not_connected",
  "not_required",
] as const;
const INTEGRATION_SORT_DIRECTIONS = ["asc", "desc"] as const;

type CuratedConnectionKind = (typeof CURATED_CONNECTION_KINDS)[number];
type CuratedConnectionStatus = (typeof CURATED_CONNECTION_STATUSES)[number];
type ConfiguredConnectionState = (typeof CONFIGURED_CONNECTION_STATES)[number];
type IntegrationSortDirection = (typeof INTEGRATION_SORT_DIRECTIONS)[number];
type ConfiguredIntegrationFilterProperty = "auth_kind" | "connection_state";
type ConfiguredIntegrationSortField = "name" | "installed_at" | "connections";
type IntegrationConnectionFilterProperty = "connection_kind" | "status";
type IntegrationConnectionSortField =
  "vendor" | "status" | "updated_at" | "expires_at";

interface ConfiguredIntegrationListItem {
  activeConnectionCount: number;
  connectionCount: number;
  connectionState: ConfiguredConnectionState;
  installation: CuratedInstallation;
}

interface ConfiguredIntegrationQuery {
  direction: IntegrationSortDirection;
  filters: FilterGroup<ConfiguredIntegrationFilterProperty>;
  search: string;
  sortBy: ConfiguredIntegrationSortField;
}

interface IntegrationConnectionQuery {
  direction: IntegrationSortDirection;
  filters: FilterGroup<IntegrationConnectionFilterProperty>;
  search: string;
  sortBy: IntegrationConnectionSortField;
}

export type {
  ConfiguredConnectionState,
  ConfiguredIntegrationFilterProperty,
  ConfiguredIntegrationListItem,
  ConfiguredIntegrationQuery,
  CuratedAuthKind,
  CuratedConnection,
  CuratedConnectionKind,
  CuratedConnectionStatus,
  CuratedCredentialInput,
  CuratedExecutionMode,
  CuratedInstallation,
  CuratedInstalledTool,
  CuratedVendor,
  CuratedVendorDetail,
  IntegrationCatalogQuery,
  IntegrationConnectionFilterProperty,
  IntegrationConnectionQuery,
  IntegrationConnectionSortField,
  IntegrationDraftContext,
  IntegrationInstallDraftValues,
  IntegrationSortDirection,
  ConfiguredIntegrationSortField,
  StoredIntegrationDraft,
};
export {
  CONFIGURED_CONNECTION_STATES,
  CURATED_AUTH_KINDS,
  CURATED_CONNECTION_KINDS,
  CURATED_CONNECTION_STATUSES,
  INTEGRATION_SORT_DIRECTIONS,
};
