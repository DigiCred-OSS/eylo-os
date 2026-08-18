import type {
  ConfiguredConnectionState,
  ConfiguredIntegrationFilterProperty,
  ConfiguredIntegrationListItem,
  ConfiguredIntegrationQuery,
  CuratedConnection,
  CuratedInstallation,
  IntegrationConnectionFilterProperty,
  IntegrationConnectionQuery,
  IntegrationSortDirection,
} from "@/features/integrations/integrations.types";
import {
  CONFIGURED_CONNECTION_STATES,
  CURATED_AUTH_KINDS,
  CURATED_CONNECTION_KINDS,
  CURATED_CONNECTION_STATUSES,
  INTEGRATION_SORT_DIRECTIONS,
} from "@/features/integrations/integrations.types";
import {
  applyFilters,
  createEmptyFilterGroup,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterGroup,
  type FilterSchema,
} from "@/lib/filters";

const CONFIGURED_FILTER_ROOT_ID = "configured-integration-main-filters";
const CONNECTION_FILTER_ROOT_ID = "integration-connection-main-filters";

const DEFAULT_CONFIGURED_INTEGRATION_QUERY: ConfiguredIntegrationQuery = {
  direction: "asc",
  filters: createEmptyFilterGroup<ConfiguredIntegrationFilterProperty>(
    CONFIGURED_FILTER_ROOT_ID,
  ),
  search: "",
  sortBy: "name",
};

const DEFAULT_INTEGRATION_CONNECTION_QUERY: IntegrationConnectionQuery = {
  direction: "desc",
  filters: createEmptyFilterGroup<IntegrationConnectionFilterProperty>(
    CONNECTION_FILTER_ROOT_ID,
  ),
  search: "",
  sortBy: "updated_at",
};

function createConfiguredIntegrationItems(
  installations: readonly CuratedInstallation[],
  connections: readonly CuratedConnection[],
): ConfiguredIntegrationListItem[] {
  const connectionsByVendor = new Map<string, CuratedConnection[]>();
  for (const connection of connections) {
    const vendorConnections = connectionsByVendor.get(connection.vendor) ?? [];
    vendorConnections.push(connection);
    connectionsByVendor.set(connection.vendor, vendorConnections);
  }

  return installations.map((installation) => {
    const vendorConnections =
      connectionsByVendor.get(installation.vendor) ?? [];
    const activeConnectionCount = vendorConnections.filter(
      (connection) => connection.status === "ACTIVE",
    ).length;
    return {
      activeConnectionCount,
      connectionCount: vendorConnections.length,
      connectionState: configuredConnectionState(
        installation,
        vendorConnections.length,
        activeConnectionCount,
      ),
      installation,
    };
  });
}

function parseConfiguredIntegrationQuery(
  params: URLSearchParams,
): ConfiguredIntegrationQuery {
  return {
    direction:
      parseKnownValue(params.get("direction"), INTEGRATION_SORT_DIRECTIONS) ??
      DEFAULT_CONFIGURED_INTEGRATION_QUERY.direction,
    filters: createConfiguredFilterTree(
      parseKnownValues(params.getAll("auth"), CURATED_AUTH_KINDS),
      parseKnownValues(
        params.getAll("connection"),
        CONFIGURED_CONNECTION_STATES,
      ),
    ),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(params.get("sort"), [
        "name",
        "installed_at",
        "connections",
      ] as const) ?? DEFAULT_CONFIGURED_INTEGRATION_QUERY.sortBy,
  };
}

function buildConfiguredIntegrationSearchParams(
  query: ConfiguredIntegrationQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  appendKnownValues(
    params,
    "auth",
    getFilterValues(query.filters, "auth_kind"),
    CURATED_AUTH_KINDS,
  );
  appendKnownValues(
    params,
    "connection",
    getFilterValues(query.filters, "connection_state"),
    CONFIGURED_CONNECTION_STATES,
  );
  if (query.sortBy !== DEFAULT_CONFIGURED_INTEGRATION_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_CONFIGURED_INTEGRATION_QUERY.direction) {
    params.set("direction", query.direction);
  }
  return params;
}

function applyConfiguredIntegrationQuery(
  items: readonly ConfiguredIntegrationListItem[],
  query: ConfiguredIntegrationQuery,
  schema: FilterSchema<
    ConfiguredIntegrationListItem,
    ConfiguredIntegrationFilterProperty,
    unknown
  >,
): ConfiguredIntegrationListItem[] {
  const search = query.search.toLocaleLowerCase();
  const visible = applyFilters(items, query.filters, schema).filter((item) => {
    if (search === "") return true;
    const { installation } = item;
    return `${installation.displayName} ${installation.vendor} ${installation.instanceUrl ?? ""} ${installation.oauthTenant ?? ""} ${installation.authKind}`
      .toLocaleLowerCase()
      .includes(search);
  });
  return visible.sort((left, right) => {
    if (query.sortBy === "connections") {
      return applyDirection(
        left.activeConnectionCount - right.activeConnectionCount ||
          left.connectionCount - right.connectionCount,
        query.direction,
      );
    }
    if (query.sortBy === "installed_at") {
      return compareDates(
        left.installation.installedAt,
        right.installation.installedAt,
        query.direction,
      );
    }
    return applyDirection(
      compareText(
        left.installation.displayName,
        right.installation.displayName,
      ),
      query.direction,
    );
  });
}

function parseIntegrationConnectionQuery(
  params: URLSearchParams,
): IntegrationConnectionQuery {
  return {
    direction:
      parseKnownValue(params.get("direction"), INTEGRATION_SORT_DIRECTIONS) ??
      DEFAULT_INTEGRATION_CONNECTION_QUERY.direction,
    filters: createConnectionFilterTree(
      parseKnownValues(params.getAll("status"), CURATED_CONNECTION_STATUSES),
      parseKnownValues(params.getAll("owner"), CURATED_CONNECTION_KINDS),
    ),
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sortBy:
      parseKnownValue(params.get("sort"), [
        "vendor",
        "status",
        "updated_at",
        "expires_at",
      ] as const) ?? DEFAULT_INTEGRATION_CONNECTION_QUERY.sortBy,
  };
}

function buildIntegrationConnectionSearchParams(
  query: IntegrationConnectionQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search !== "") params.set("q", query.search);
  appendKnownValues(
    params,
    "status",
    getFilterValues(query.filters, "status"),
    CURATED_CONNECTION_STATUSES,
  );
  appendKnownValues(
    params,
    "owner",
    getFilterValues(query.filters, "connection_kind"),
    CURATED_CONNECTION_KINDS,
  );
  if (query.sortBy !== DEFAULT_INTEGRATION_CONNECTION_QUERY.sortBy) {
    params.set("sort", query.sortBy);
  }
  if (query.direction !== DEFAULT_INTEGRATION_CONNECTION_QUERY.direction) {
    params.set("direction", query.direction);
  }
  return params;
}

function applyIntegrationConnectionQuery(
  connections: readonly CuratedConnection[],
  query: IntegrationConnectionQuery,
  schema: FilterSchema<
    CuratedConnection,
    IntegrationConnectionFilterProperty,
    unknown
  >,
): CuratedConnection[] {
  const search = query.search.toLocaleLowerCase();
  const visible = applyFilters(connections, query.filters, schema).filter(
    (connection) =>
      search === "" ||
      `${connection.displayName ?? ""} ${connection.vendor} ${connection.id} ${connection.owner.displayName}`
        .toLocaleLowerCase()
        .includes(search),
  );
  return visible.sort((left, right) => {
    if (query.sortBy === "updated_at") {
      return compareDates(
        left.updatedAt ?? left.createdAt,
        right.updatedAt ?? right.createdAt,
        query.direction,
      );
    }
    if (query.sortBy === "expires_at") {
      return compareDates(
        left.credentialsExpiresAt,
        right.credentialsExpiresAt,
        query.direction,
      );
    }
    if (query.sortBy === "status") {
      return applyDirection(
        compareText(left.status, right.status),
        query.direction,
      );
    }
    return applyDirection(
      compareText(
        left.displayName ?? left.vendor,
        right.displayName ?? right.vendor,
      ),
      query.direction,
    );
  });
}

function hasConfiguredIntegrationFilters(
  query: ConfiguredIntegrationQuery,
): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function hasIntegrationConnectionFilters(
  query: IntegrationConnectionQuery,
): boolean {
  return query.search !== "" || query.filters.children.length > 0;
}

function configuredConnectionState(
  installation: CuratedInstallation,
  connectionCount: number,
  activeConnectionCount: number,
): ConfiguredConnectionState {
  if (installation.authKind === "no_auth") return "not_required";
  if (activeConnectionCount > 0) return "active";
  return connectionCount > 0 ? "attention" : "not_connected";
}

function createConfiguredFilterTree(
  authKinds: readonly string[],
  states: readonly string[],
): FilterGroup<ConfiguredIntegrationFilterProperty> {
  return createFilterTree(CONFIGURED_FILTER_ROOT_ID, [
    createFilterCondition("auth_kind", authKinds),
    createFilterCondition("connection_state", states),
  ]);
}

function createConnectionFilterTree(
  statuses: readonly string[],
  kinds: readonly string[],
): FilterGroup<IntegrationConnectionFilterProperty> {
  return createFilterTree(CONNECTION_FILTER_ROOT_ID, [
    createFilterCondition("status", statuses),
    createFilterCondition("connection_kind", kinds),
  ]);
}

function createFilterTree<Property extends string>(
  id: string,
  conditions: FilterCondition<Property>[],
): FilterGroup<Property> {
  return {
    children: conditions.filter((condition) => condition.values.length > 0),
    id,
    op: "and",
    type: "group",
  };
}

function createFilterCondition<Property extends string>(
  property: Property,
  values: readonly string[],
): FilterCondition<Property> {
  return {
    id: `${property}-main-filter`,
    operator: normalizeFilterOperator("is", "multi-select", values.length),
    property,
    type: "condition",
    values,
  };
}

function getFilterValues<Property extends string>(
  filterTree: FilterGroup<Property>,
  property: Property,
): readonly string[] {
  const condition = filterTree.children.find(
    (node) => node.type === "condition" && node.property === property,
  );
  return condition?.type === "condition" ? condition.values : [];
}

function appendKnownValues<T extends string>(
  params: URLSearchParams,
  key: string,
  values: readonly string[],
  knownValues: readonly T[],
): void {
  for (const value of knownValues) {
    if (values.includes(value)) params.append(key, value);
  }
}

function parseKnownValue<T extends string>(
  value: string | null,
  knownValues: readonly T[],
): T | null {
  return value !== null && knownValues.includes(value as T)
    ? (value as T)
    : null;
}

function parseKnownValues<T extends string>(
  values: readonly string[],
  knownValues: readonly T[],
): T[] {
  return knownValues.filter((knownValue) => values.includes(knownValue));
}

function compareDates(
  left: string | null | undefined,
  right: string | null | undefined,
  direction: IntegrationSortDirection,
): number {
  const leftTime = toTime(left);
  const rightTime = toTime(right);
  if (leftTime === null && rightTime === null) return 0;
  if (leftTime === null) return 1;
  if (rightTime === null) return -1;
  return applyDirection(leftTime - rightTime, direction);
}

function toTime(value: string | null | undefined): number | null {
  if (!value) return null;
  const time = Date.parse(value);
  return Number.isNaN(time) ? null : time;
}

function compareText(left: string, right: string): number {
  return left.localeCompare(right, undefined, { sensitivity: "base" });
}

function applyDirection(
  comparison: number,
  direction: IntegrationSortDirection,
): number {
  return direction === "asc" ? comparison : -comparison;
}

export {
  applyConfiguredIntegrationQuery,
  applyIntegrationConnectionQuery,
  buildConfiguredIntegrationSearchParams,
  buildIntegrationConnectionSearchParams,
  createConfiguredIntegrationItems,
  DEFAULT_CONFIGURED_INTEGRATION_QUERY,
  DEFAULT_INTEGRATION_CONNECTION_QUERY,
  hasConfiguredIntegrationFilters,
  hasIntegrationConnectionFilters,
  parseConfiguredIntegrationQuery,
  parseIntegrationConnectionQuery,
};
