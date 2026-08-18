import type {
  CuratedAuthKind,
  CuratedVendor,
  IntegrationCatalogQuery,
} from "@/features/integrations/integrations.types";

const AUTH_KINDS = [
  "no_auth",
  "api_key",
  "basic",
  "oauth2",
] as const satisfies readonly CuratedAuthKind[];
const DEFAULT_INTEGRATION_QUERY: IntegrationCatalogQuery = {
  auth: "all",
  category: "all",
  installed: "all",
  search: "",
  sort: "name",
};

function parseIntegrationCatalogQuery(
  params: URLSearchParams,
  categories: readonly string[],
): IntegrationCatalogQuery {
  const auth = params.get("auth");
  const category = params.get("category");
  const installed = params.get("installed");
  const sort = params.get("sort");
  return {
    auth:
      auth !== null && AUTH_KINDS.includes(auth as CuratedAuthKind)
        ? (auth as CuratedAuthKind)
        : "all",
    category:
      category !== null && categories.includes(category) ? category : "all",
    installed:
      installed === "configured" || installed === "available"
        ? installed
        : "all",
    search: params.get("q")?.trim().slice(0, 100) ?? "",
    sort: sort === "tools" ? "tools" : "name",
  };
}

function buildIntegrationCatalogSearchParams(
  query: IntegrationCatalogQuery,
): URLSearchParams {
  const params = new URLSearchParams();
  if (query.search) params.set("q", query.search);
  if (query.category !== "all") params.set("category", query.category);
  if (query.auth !== "all") params.set("auth", query.auth);
  if (query.installed !== "all") params.set("installed", query.installed);
  if (query.sort !== "name") params.set("sort", query.sort);
  return params;
}

function applyIntegrationCatalogQuery(
  vendors: readonly CuratedVendor[],
  query: IntegrationCatalogQuery,
): CuratedVendor[] {
  const search = query.search.toLocaleLowerCase();
  return vendors
    .filter((vendor) => {
      if (
        search &&
        !`${vendor.displayName} ${vendor.description} ${vendor.vendor} ${(vendor.categories ?? []).join(" ")}`
          .toLocaleLowerCase()
          .includes(search)
      ) {
        return false;
      }
      if (
        query.category !== "all" &&
        !(vendor.categories ?? []).includes(query.category)
      ) {
        return false;
      }
      if (
        query.auth !== "all" &&
        !(vendor.authKinds ?? []).includes(query.auth)
      ) {
        return false;
      }
      if (query.installed === "configured" && !vendor.installed) return false;
      if (query.installed === "available" && vendor.installed) return false;
      return true;
    })
    .sort((left, right) => {
      if (query.sort === "tools" && left.toolCount !== right.toolCount) {
        return right.toolCount - left.toolCount;
      }
      return left.displayName.localeCompare(right.displayName, undefined, {
        sensitivity: "base",
      });
    });
}

export {
  applyIntegrationCatalogQuery,
  buildIntegrationCatalogSearchParams,
  DEFAULT_INTEGRATION_QUERY,
  parseIntegrationCatalogQuery,
};
