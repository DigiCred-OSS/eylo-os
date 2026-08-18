import { Eye, Plug, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { useRootStore } from "@/app/use-root-store";
import {
  AppliedFilterBar,
  CollectionToolbar,
  FilterControl,
  SortControl,
} from "@/components/filters";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatIntegrationDate } from "@/features/integrations/integration-formatters";
import {
  CONFIGURED_CONNECTION_STATE_LABELS,
  CONFIGURED_INTEGRATION_FILTER_SCHEMA,
  CONFIGURED_INTEGRATION_SORT_OPTIONS,
  INTEGRATION_AUTH_LABELS,
} from "@/features/integrations/integration-list-controls";
import {
  applyConfiguredIntegrationQuery,
  buildConfiguredIntegrationSearchParams,
  createConfiguredIntegrationItems,
  DEFAULT_CONFIGURED_INTEGRATION_QUERY,
  hasConfiguredIntegrationFilters,
  parseConfiguredIntegrationQuery,
} from "@/features/integrations/integration-lists.query";
import { integrationVendorPath } from "@/features/integrations/integration-navigation";
import type {
  ConfiguredIntegrationListItem,
  ConfiguredIntegrationQuery,
} from "@/features/integrations/integrations.types";

const ConfiguredIntegrationsPage = observer(
  function ConfiguredIntegrationsPage() {
    const { integrations } = useRootStore();
    const { organizationId } = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const location = useLocation();
    const navigate = useNavigate();
    const paramsKey = searchParams.toString();
    const query = useMemo(
      () => parseConfiguredIntegrationQuery(new URLSearchParams(paramsKey)),
      [paramsKey],
    );
    const items = useMemo(
      () =>
        createConfiguredIntegrationItems(
          integrations.installations,
          integrations.connections,
        ),
      [integrations.connections, integrations.installations],
    );
    const visibleItems = useMemo(
      () =>
        applyConfiguredIntegrationQuery(
          items,
          query,
          CONFIGURED_INTEGRATION_FILTER_SCHEMA,
        ),
      [items, query],
    );
    const [searchDraft, setSearchDraft] = useState(query.search);

    useEffect(() => setSearchDraft(query.search), [query.search]);
    useEffect(() => {
      if (organizationId) {
        void Promise.all([
          integrations.loadInstallations(organizationId),
          integrations.loadConnections(organizationId),
        ]);
      }
    }, [integrations, organizationId]);

    if (!organizationId) return null;
    const activeOrganizationId = organizationId;
    const isLoading =
      integrations.isInstallationsLoading || integrations.isConnectionsLoading;
    const hasFilters = hasConfiguredIntegrationFilters(query);

    function setQuery(next: ConfiguredIntegrationQuery): void {
      setSearchParams(buildConfiguredIntegrationSearchParams(next));
    }

    function updateQuery(patch: Partial<ConfiguredIntegrationQuery>): void {
      setQuery({ ...query, ...patch });
    }

    function browseMarketplace(): void {
      void navigate(`/org/${activeOrganizationId}/integrations`);
    }

    function openVendor(vendor: string): void {
      const returnTo = `${location.pathname}${location.search}`;
      void navigate(
        integrationVendorPath(activeOrganizationId, vendor, returnTo),
      );
    }

    return (
      <section
        className="min-w-0 space-y-6 p-4 sm:p-6"
        aria-labelledby="configured-integrations-title"
      >
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <h1
              id="configured-integrations-title"
              className="text-2xl font-semibold tracking-tight"
            >
              Configured integrations
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Review installed vendors, authorization modes, and whether a
              usable connection is available.
            </p>
          </div>
          <Button variant="outline" onClick={browseMarketplace}>
            <Plug aria-hidden="true" />
            Browse integrations
          </Button>
        </header>

        <CollectionLoadNotice
          connectionError={integrations.connectionsErrorMessage}
          installationError={integrations.installationsErrorMessage}
          hasInstallations={integrations.installations.length > 0}
          onRetry={() =>
            void Promise.all([
              integrations.loadInstallations(activeOrganizationId),
              integrations.loadConnections(activeOrganizationId),
            ])
          }
        />

        <CollectionToolbar
          listLabel="Configured integrations"
          search={
            <form
              className="relative w-full sm:max-w-sm"
              role="search"
              onSubmit={(event) => {
                event.preventDefault();
                updateQuery({ search: searchDraft.trim().slice(0, 100) });
              }}
            >
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                className="pr-20 pl-9"
                aria-label="Search configured integrations"
                maxLength={100}
                placeholder="Search configured integrations"
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
              />
              <Button
                className="absolute top-0 right-0 rounded-l-none"
                variant="ghost"
                type="submit"
              >
                Search
              </Button>
            </form>
          }
          filter={
            <FilterControl
              filterTree={query.filters}
              listLabel="Configured integrations"
              schema={CONFIGURED_INTEGRATION_FILTER_SCHEMA}
              onChange={(filters) => updateQuery({ filters })}
            />
          }
          sort={
            <SortControl
              direction={query.direction}
              listLabel="Configured integrations"
              options={CONFIGURED_INTEGRATION_SORT_OPTIONS}
              sort={query.sortBy}
              onDirectionChange={(direction) => updateQuery({ direction })}
              onSortChange={(sortBy) => updateQuery({ sortBy })}
            />
          }
          appliedFilters={
            <AppliedFilterBar
              filterTree={query.filters}
              listLabel="Configured integrations"
              schema={CONFIGURED_INTEGRATION_FILTER_SCHEMA}
              onChange={(filters) => updateQuery({ filters })}
            />
          }
        />

        {integrations.installationsErrorMessage !== null &&
        integrations.installations.length === 0 ? (
          <LoadFailure
            message={integrations.installationsErrorMessage}
            onRetry={() =>
              void integrations.loadInstallations(activeOrganizationId)
            }
          />
        ) : !isLoading && visibleItems.length === 0 ? (
          <ConfiguredEmptyState
            hasFilters={hasFilters}
            onBrowse={browseMarketplace}
            onClear={() => setQuery(DEFAULT_CONFIGURED_INTEGRATION_QUERY)}
          />
        ) : (
          <ConfiguredIntegrationsTable
            isLoading={isLoading}
            items={visibleItems}
            onOpen={openVendor}
          />
        )}
      </section>
    );
  },
);

function ConfiguredIntegrationsTable({
  isLoading,
  items,
  onOpen,
}: {
  isLoading: boolean;
  items: ConfiguredIntegrationListItem[];
  onOpen: (vendor: string) => void;
}) {
  return (
    <div className="border" aria-busy={isLoading}>
      <div
        className="divide-y sm:hidden"
        role="list"
        aria-label="Configured integrations"
      >
        {isLoading && items.length === 0
          ? Array.from({ length: 4 }, (_, index) => (
              <IntegrationLoadingCard key={index} />
            ))
          : items.map((item) => (
              <ConfiguredIntegrationCard
                item={item}
                key={item.installation.id}
                onOpen={onOpen}
              />
            ))}
      </div>
      <Table
        className="hidden table-fixed sm:table"
        aria-label="Configured integrations"
      >
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[31%]">Integration</TableHead>
            <TableHead className="w-[21%]">Authorization</TableHead>
            <TableHead className="w-[18%]">Connection</TableHead>
            <TableHead className="hidden w-[18%] lg:table-cell">
              Instance
            </TableHead>
            <TableHead className="hidden w-44 xl:table-cell">
              Configured
            </TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && items.length === 0
            ? Array.from({ length: 5 }, (_, index) => (
                <IntegrationLoadingRow key={index} />
              ))
            : items.map((item) => (
                <ConfiguredIntegrationRow
                  item={item}
                  key={item.installation.id}
                  onOpen={onOpen}
                />
              ))}
        </TableBody>
      </Table>
      {!isLoading || items.length > 0 ? (
        <p className="border-t px-3 py-3 text-xs text-muted-foreground">
          {items.length} configured integration{items.length === 1 ? "" : "s"}
        </p>
      ) : null}
    </div>
  );
}

function ConfiguredIntegrationRow({
  item,
  onOpen,
}: {
  item: ConfiguredIntegrationListItem;
  onOpen: (vendor: string) => void;
}) {
  const { installation } = item;
  const installedAt = formatIntegrationDate(installation.installedAt);
  return (
    <TableRow>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          className="block max-w-full break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onOpen(installation.vendor)}
        >
          {installation.displayName}
        </button>
        <code className="mt-0.5 block break-all text-xs text-muted-foreground">
          {installation.vendor}
        </code>
      </TableCell>
      <TableCell className="whitespace-normal">
        <Badge variant="outline">
          {INTEGRATION_AUTH_LABELS[installation.authKind]}
        </Badge>
      </TableCell>
      <TableCell className="whitespace-normal">
        <ConnectionState item={item} />
      </TableCell>
      <TableCell className="hidden min-w-0 whitespace-normal lg:table-cell">
        <span className="break-all text-muted-foreground">
          {installation.instanceUrl ?? "—"}
        </span>
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground xl:table-cell">
        <time dateTime={installedAt.title}>{installedAt.label}</time>
      </TableCell>
      <TableCell className="text-right">
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={`Open ${installation.displayName}`}
          title={`Open ${installation.displayName}`}
          onClick={() => onOpen(installation.vendor)}
        >
          <Eye aria-hidden="true" />
        </Button>
      </TableCell>
    </TableRow>
  );
}

function ConfiguredIntegrationCard({
  item,
  onOpen,
}: {
  item: ConfiguredIntegrationListItem;
  onOpen: (vendor: string) => void;
}) {
  const { installation } = item;
  const installedAt = formatIntegrationDate(installation.installedAt);
  return (
    <article
      className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 p-4"
      role="listitem"
    >
      <button
        className="min-w-0 text-left focus-visible:rounded-sm focus-visible:outline-2"
        type="button"
        onClick={() => onOpen(installation.vendor)}
      >
        <span className="block break-words text-sm font-medium">
          {installation.displayName}
        </span>
        <code className="mt-0.5 block break-all text-xs text-muted-foreground">
          {installation.vendor}
        </code>
        <span className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <ConnectionState item={item} />
          <Badge variant="outline">
            {INTEGRATION_AUTH_LABELS[installation.authKind]}
          </Badge>
          <span>Configured {installedAt.label}</span>
        </span>
        {installation.instanceUrl ? (
          <span className="mt-2 block break-all text-xs text-muted-foreground">
            {installation.instanceUrl}
          </span>
        ) : null}
      </button>
      <Button
        size="icon-sm"
        variant="ghost"
        aria-label={`Open ${installation.displayName}`}
        title={`Open ${installation.displayName}`}
        onClick={() => onOpen(installation.vendor)}
      >
        <Eye aria-hidden="true" />
      </Button>
    </article>
  );
}

function ConnectionState({ item }: { item: ConfiguredIntegrationListItem }) {
  const detail =
    item.connectionCount > 0
      ? `${item.activeConnectionCount} active · ${item.connectionCount} total`
      : null;
  return (
    <div className="flex flex-col items-start gap-1">
      <Badge
        variant={item.connectionState === "active" ? "secondary" : "outline"}
      >
        {CONFIGURED_CONNECTION_STATE_LABELS[item.connectionState]}
      </Badge>
      {detail ? (
        <span className="text-xs text-muted-foreground">{detail}</span>
      ) : null}
    </div>
  );
}

function CollectionLoadNotice({
  connectionError,
  hasInstallations,
  installationError,
  onRetry,
}: {
  connectionError: string | null;
  hasInstallations: boolean;
  installationError: string | null;
  onRetry: () => void;
}) {
  if (
    connectionError === null &&
    (installationError === null || !hasInstallations)
  ) {
    return null;
  }
  return (
    <div
      className="border border-warning/40 bg-warning/10 p-3 text-sm"
      role="alert"
    >
      {installationError ? `${installationError} ` : null}
      {connectionError
        ? "Connection counts may be incomplete. "
        : "Showing the last loaded configured integrations. "}
      <Button className="ml-2" size="sm" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function ConfiguredEmptyState({
  hasFilters,
  onBrowse,
  onClear,
}: {
  hasFilters: boolean;
  onBrowse: () => void;
  onClear: () => void;
}) {
  return (
    <div className="border py-16 text-center">
      <p className="text-sm font-medium">
        {hasFilters
          ? "No configured integrations match these filters"
          : "No integrations configured yet"}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        {hasFilters
          ? "Change or clear the filters to see other configurations."
          : "Choose a curated integration, then save its organization configuration."}
      </p>
      <Button
        className="mt-4"
        variant={hasFilters ? "outline" : "default"}
        onClick={hasFilters ? onClear : onBrowse}
      >
        {hasFilters ? "Clear filters" : "Browse integrations"}
      </Button>
    </div>
  );
}

function LoadFailure({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="border py-16 text-center" role="alert">
      <p className="text-sm font-medium">
        Configured integrations are unavailable
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      <Button className="mt-4" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function IntegrationLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-5 w-36 max-w-full" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-28 max-w-full" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-24 max-w-full" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-32 max-w-full" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-5 w-32 max-w-full" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function IntegrationLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-5 w-40 max-w-full" />
      <Skeleton className="h-4 w-28 max-w-full" />
      <Skeleton className="h-5 w-56 max-w-full" />
    </div>
  );
}

export { ConfiguredIntegrationsPage };
