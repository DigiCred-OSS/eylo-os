import {
  CalendarDays,
  CircleDot,
  KeyRound,
  Link2,
  Type,
  UserRound,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  ConfiguredIntegrationFilterProperty,
  ConfiguredIntegrationListItem,
  ConfiguredIntegrationSortField,
  CuratedAuthKind,
  CuratedConnection,
  CuratedConnectionKind,
  CuratedConnectionStatus,
  IntegrationConnectionFilterProperty,
  IntegrationConnectionSortField,
} from "@/features/integrations/integrations.types";
import {
  CURATED_AUTH_KINDS,
  CURATED_CONNECTION_KINDS,
  CURATED_CONNECTION_STATUSES,
} from "@/features/integrations/integrations.types";

const INTEGRATION_AUTH_LABELS: Record<CuratedAuthKind, string> = {
  api_key: "API key",
  basic: "Username + password",
  no_auth: "No authorization",
  oauth2: "OAuth 2.0",
};

const CONNECTION_KIND_LABELS: Record<CuratedConnectionKind, string> = {
  CONTACT: "End user",
  ORGANIZATION: "Organization",
};

const CONNECTION_STATUS_LABELS: Record<CuratedConnectionStatus, string> = {
  ACTIVE: "Active",
  FAILED: "Failed",
  INACTIVE: "Inactive",
  INITIATED: "Initiated",
  REVOKED: "Revoked",
};

const CONFIGURED_CONNECTION_STATE_LABELS = {
  active: "Active connection",
  attention: "Needs attention",
  not_connected: "Not connected",
  not_required: "Not required",
} as const;

const CONFIGURED_INTEGRATION_FILTER_SCHEMA = [
  {
    accessor: (item: ConfiguredIntegrationListItem) =>
      item.installation.authKind,
    icon: KeyRound,
    keywords: ["authorization", "credentials"],
    label: "Authorization",
    operators: ["is"],
    options: CURATED_AUTH_KINDS.map((authKind) => ({
      label: INTEGRATION_AUTH_LABELS[authKind],
      value: authKind,
    })),
    property: "auth_kind",
    valueType: "multi-select",
  },
  {
    accessor: (item: ConfiguredIntegrationListItem) => item.connectionState,
    icon: Link2,
    keywords: ["connection", "usage", "connected"],
    label: "Connection",
    operators: ["is"],
    options: Object.entries(CONFIGURED_CONNECTION_STATE_LABELS).map(
      ([value, label]) => ({ label, value }),
    ),
    property: "connection_state",
    valueType: "multi-select",
  },
] as const satisfies FilterUiSchema<
  ConfiguredIntegrationListItem,
  ConfiguredIntegrationFilterProperty
>;

const CONFIGURED_INTEGRATION_SORT_OPTIONS = [
  { icon: Type, label: "Name", value: "name" },
  { icon: CalendarDays, label: "Configured", value: "installed_at" },
  { icon: Link2, label: "Connections", value: "connections" },
] as const satisfies readonly SortOption<ConfiguredIntegrationSortField>[];

const INTEGRATION_CONNECTION_FILTER_SCHEMA = [
  {
    accessor: (connection: CuratedConnection) => connection.status,
    icon: CircleDot,
    keywords: ["lifecycle", "health"],
    label: "Status",
    operators: ["is"],
    options: CURATED_CONNECTION_STATUSES.map((status) => ({
      label: CONNECTION_STATUS_LABELS[status],
      value: status,
    })),
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (connection: CuratedConnection) => connection.connectionKind,
    icon: UserRound,
    keywords: ["owner", "scope", "personal"],
    label: "Owner",
    operators: ["is"],
    options: CURATED_CONNECTION_KINDS.map((kind) => ({
      label: CONNECTION_KIND_LABELS[kind],
      value: kind,
    })),
    property: "connection_kind",
    valueType: "multi-select",
  },
] as const satisfies FilterUiSchema<
  CuratedConnection,
  IntegrationConnectionFilterProperty
>;

const INTEGRATION_CONNECTION_SORT_OPTIONS = [
  { icon: Type, label: "Integration", value: "vendor" },
  { icon: CircleDot, label: "Status", value: "status" },
  { icon: CalendarDays, label: "Updated", value: "updated_at" },
  { icon: CalendarDays, label: "Expiry", value: "expires_at" },
] as const satisfies readonly SortOption<IntegrationConnectionSortField>[];

export {
  CONFIGURED_CONNECTION_STATE_LABELS,
  CONFIGURED_INTEGRATION_FILTER_SCHEMA,
  CONFIGURED_INTEGRATION_SORT_OPTIONS,
  CONNECTION_KIND_LABELS,
  CONNECTION_STATUS_LABELS,
  INTEGRATION_AUTH_LABELS,
  INTEGRATION_CONNECTION_FILTER_SCHEMA,
  INTEGRATION_CONNECTION_SORT_OPTIONS,
};
