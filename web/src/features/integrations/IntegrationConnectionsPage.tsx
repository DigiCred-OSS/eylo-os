import { Ellipsis, Eye, Link2, Search, Trash2 } from "lucide-react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { ConnectionDeleteDialog } from "@/features/integrations/ConnectionDeleteDialog";
import {
  formatIntegrationDate,
  formatIntegrationIdentifier,
} from "@/features/integrations/integration-formatters";
import {
  CONNECTION_KIND_LABELS,
  CONNECTION_STATUS_LABELS,
  INTEGRATION_CONNECTION_FILTER_SCHEMA,
  INTEGRATION_CONNECTION_SORT_OPTIONS,
} from "@/features/integrations/integration-list-controls";
import {
  applyIntegrationConnectionQuery,
  buildIntegrationConnectionSearchParams,
  DEFAULT_INTEGRATION_CONNECTION_QUERY,
  hasIntegrationConnectionFilters,
  parseIntegrationConnectionQuery,
} from "@/features/integrations/integration-lists.query";
import {
  configuredIntegrationsPath,
  integrationVendorPath,
} from "@/features/integrations/integration-navigation";
import type {
  CuratedConnection,
  CuratedConnectionKind,
  CuratedConnectionStatus,
  IntegrationConnectionQuery,
} from "@/features/integrations/integrations.types";

const IntegrationConnectionsPage = observer(
  function IntegrationConnectionsPage() {
    const { integrations } = useRootStore();
    const { organizationId } = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const location = useLocation();
    const navigate = useNavigate();
    const paramsKey = searchParams.toString();
    const query = useMemo(
      () => parseIntegrationConnectionQuery(new URLSearchParams(paramsKey)),
      [paramsKey],
    );
    const visibleConnections = useMemo(
      () =>
        applyIntegrationConnectionQuery(
          integrations.connections,
          query,
          INTEGRATION_CONNECTION_FILTER_SCHEMA,
        ),
      [integrations.connections, query],
    );
    const [searchDraft, setSearchDraft] = useState(query.search);
    const [connectionPendingDelete, setConnectionPendingDelete] =
      useState<CuratedConnection | null>(null);

    useEffect(() => setSearchDraft(query.search), [query.search]);
    useEffect(() => {
      if (organizationId) void integrations.loadConnections(organizationId);
    }, [integrations, organizationId]);

    if (!organizationId) return null;
    const activeOrganizationId = organizationId;
    const hasFilters = hasIntegrationConnectionFilters(query);

    function setQuery(next: IntegrationConnectionQuery): void {
      setSearchParams(buildIntegrationConnectionSearchParams(next));
    }

    function updateQuery(patch: Partial<IntegrationConnectionQuery>): void {
      setQuery({ ...query, ...patch });
    }

    function openConfiguredIntegrations(): void {
      void navigate(configuredIntegrationsPath(activeOrganizationId));
    }

    function openVendor(vendor: string): void {
      if (vendor === "unknown") return;
      const returnTo = `${location.pathname}${location.search}`;
      void navigate(
        integrationVendorPath(activeOrganizationId, vendor, returnTo),
      );
    }

    async function deleteConnection(): Promise<boolean> {
      if (!connectionPendingDelete) return false;
      const deleted = await integrations.deleteConnection(
        activeOrganizationId,
        connectionPendingDelete.id,
      );
      if (deleted) setConnectionPendingDelete(null);
      return deleted;
    }

    function requestConnectionDeletion(connection: CuratedConnection): void {
      integrations.clearActionError();
      setConnectionPendingDelete(connection);
    }

    return (
      <section
        className="min-w-0 space-y-6 p-4 sm:p-6"
        aria-labelledby="integration-connections-title"
      >
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <h1
              id="integration-connections-title"
              className="text-2xl font-semibold tracking-tight"
            >
              Connections
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Review the organization and end-user accounts that authorize
              configured integration tools.
            </p>
          </div>
          <Button variant="outline" onClick={openConfiguredIntegrations}>
            <Link2 aria-hidden="true" />
            Configured integrations
          </Button>
        </header>

        {integrations.actionErrorMessage && !connectionPendingDelete ? (
          <div
            className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
            role="alert"
          >
            {integrations.actionErrorMessage}
          </div>
        ) : null}

        {integrations.connectionsErrorMessage !== null &&
        integrations.connections.length > 0 ? (
          <div
            className="border border-warning/40 bg-warning/10 p-3 text-sm"
            role="alert"
          >
            Showing the last loaded connections.{" "}
            {integrations.connectionsErrorMessage}
            <Button
              className="ml-2"
              size="sm"
              variant="outline"
              onClick={() =>
                void integrations.loadConnections(activeOrganizationId)
              }
            >
              Try again
            </Button>
          </div>
        ) : null}

        <CollectionToolbar
          listLabel="Integration connections"
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
                aria-label="Search integration connections"
                maxLength={100}
                placeholder="Search connections"
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
              listLabel="Integration connections"
              schema={INTEGRATION_CONNECTION_FILTER_SCHEMA}
              onChange={(filters) => updateQuery({ filters })}
            />
          }
          sort={
            <SortControl
              direction={query.direction}
              listLabel="Integration connections"
              options={INTEGRATION_CONNECTION_SORT_OPTIONS}
              sort={query.sortBy}
              onDirectionChange={(direction) => updateQuery({ direction })}
              onSortChange={(sortBy) => updateQuery({ sortBy })}
            />
          }
          appliedFilters={
            <AppliedFilterBar
              filterTree={query.filters}
              listLabel="Integration connections"
              schema={INTEGRATION_CONNECTION_FILTER_SCHEMA}
              onChange={(filters) => updateQuery({ filters })}
            />
          }
        />

        {integrations.connectionsErrorMessage !== null &&
        integrations.connections.length === 0 ? (
          <LoadFailure
            message={integrations.connectionsErrorMessage}
            onRetry={() =>
              void integrations.loadConnections(activeOrganizationId)
            }
          />
        ) : !integrations.isConnectionsLoading &&
          visibleConnections.length === 0 ? (
          <ConnectionsEmptyState
            hasFilters={hasFilters}
            onClear={() => setQuery(DEFAULT_INTEGRATION_CONNECTION_QUERY)}
            onOpenConfigured={openConfiguredIntegrations}
          />
        ) : (
          <ConnectionsTable
            connections={visibleConnections}
            isLoading={integrations.isConnectionsLoading}
            onDelete={requestConnectionDeletion}
            onOpen={openVendor}
          />
        )}

        <ConnectionDeleteDialog
          connection={connectionPendingDelete}
          errorMessage={integrations.actionErrorMessage}
          isDeleting={integrations.isActing}
          vendorName={connectionName(connectionPendingDelete)}
          onConfirm={deleteConnection}
          onOpenChange={(open) => {
            if (!open) {
              integrations.clearActionError();
              setConnectionPendingDelete(null);
            }
          }}
        />
      </section>
    );
  },
);

function ConnectionsTable({
  connections,
  isLoading,
  onDelete,
  onOpen,
}: {
  connections: CuratedConnection[];
  isLoading: boolean;
  onDelete: (connection: CuratedConnection) => void;
  onOpen: (vendor: string) => void;
}) {
  return (
    <div className="border" aria-busy={isLoading}>
      <div
        className="divide-y sm:hidden"
        role="list"
        aria-label="Integration connections"
      >
        {isLoading && connections.length === 0
          ? Array.from({ length: 4 }, (_, index) => (
              <ConnectionLoadingCard key={index} />
            ))
          : connections.map((connection) => (
              <ConnectionCard
                connection={connection}
                key={connection.id}
                onDelete={onDelete}
                onOpen={onOpen}
              />
            ))}
      </div>
      <Table
        className="hidden table-fixed sm:table"
        aria-label="Integration connections"
      >
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[30%]">Integration</TableHead>
            <TableHead className="w-[23%]">Owner</TableHead>
            <TableHead className="w-[15%]">Status</TableHead>
            <TableHead className="hidden w-44 lg:table-cell">Expires</TableHead>
            <TableHead className="hidden w-44 xl:table-cell">Updated</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && connections.length === 0
            ? Array.from({ length: 5 }, (_, index) => (
                <ConnectionLoadingRow key={index} />
              ))
            : connections.map((connection) => (
                <ConnectionRow
                  connection={connection}
                  key={connection.id}
                  onDelete={onDelete}
                  onOpen={onOpen}
                />
              ))}
        </TableBody>
      </Table>
      {!isLoading || connections.length > 0 ? (
        <p className="border-t px-3 py-3 text-xs text-muted-foreground">
          {connections.length} connection{connections.length === 1 ? "" : "s"}
        </p>
      ) : null}
    </div>
  );
}

function ConnectionRow({
  connection,
  onDelete,
  onOpen,
}: {
  connection: CuratedConnection;
  onDelete: (connection: CuratedConnection) => void;
  onOpen: (vendor: string) => void;
}) {
  const updated = formatIntegrationDate(
    connection.updatedAt ?? connection.createdAt,
  );
  return (
    <TableRow>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          className="block max-w-full break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2 disabled:no-underline disabled:opacity-70"
          type="button"
          disabled={connection.vendor === "unknown"}
          onClick={() => onOpen(connection.vendor)}
        >
          {connectionName(connection)}
        </button>
        <code className="mt-0.5 block break-all text-xs text-muted-foreground">
          {connection.vendor}
        </code>
      </TableCell>
      <TableCell className="min-w-0 whitespace-normal">
        <ConnectionOwner connection={connection} />
      </TableCell>
      <TableCell className="whitespace-normal">
        <ConnectionStatusBadge status={connection.status} />
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground lg:table-cell">
        <ConnectionExpiry value={connection.credentialsExpiresAt} />
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground xl:table-cell">
        <time dateTime={updated.title}>{updated.label}</time>
      </TableCell>
      <TableCell className="text-right">
        <ConnectionActions
          connection={connection}
          onDelete={onDelete}
          onOpen={onOpen}
        />
      </TableCell>
    </TableRow>
  );
}

function ConnectionCard({
  connection,
  onDelete,
  onOpen,
}: {
  connection: CuratedConnection;
  onDelete: (connection: CuratedConnection) => void;
  onOpen: (vendor: string) => void;
}) {
  const updated = formatIntegrationDate(
    connection.updatedAt ?? connection.createdAt,
  );
  return (
    <article
      className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 p-4"
      role="listitem"
    >
      <button
        className="min-w-0 text-left focus-visible:rounded-sm focus-visible:outline-2 disabled:opacity-70"
        type="button"
        disabled={connection.vendor === "unknown"}
        onClick={() => onOpen(connection.vendor)}
      >
        <span className="block break-words text-sm font-medium">
          {connectionName(connection)}
        </span>
        <code className="mt-0.5 block break-all text-xs text-muted-foreground">
          {connection.vendor}
        </code>
        <span className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <ConnectionStatusBadge status={connection.status} />
          <ConnectionKindBadge kind={connection.connectionKind} />
          <span>Updated {updated.label}</span>
        </span>
        <span className="mt-2 block break-words text-xs text-muted-foreground">
          {connection.owner.displayName}
        </span>
      </button>
      <ConnectionActions
        connection={connection}
        onDelete={onDelete}
        onOpen={onOpen}
      />
    </article>
  );
}

function ConnectionActions({
  connection,
  onDelete,
  onOpen,
}: {
  connection: CuratedConnection;
  onDelete: (connection: CuratedConnection) => void;
  onOpen: (vendor: string) => void;
}) {
  const name = connectionName(connection);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label={`Actions for ${name}`}
            title={`Actions for ${name}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {connection.vendor === "unknown" ? null : (
          <DropdownMenuItem onClick={() => onOpen(connection.vendor)}>
            <Eye aria-hidden="true" />
            Open integration
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => onDelete(connection)}
        >
          <Trash2 aria-hidden="true" />
          Delete connection
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ConnectionOwner({ connection }: { connection: CuratedConnection }) {
  return (
    <div className="flex min-w-0 flex-col items-start gap-1">
      <p className="break-words">{connection.owner.displayName}</p>
      <ConnectionKindBadge kind={connection.connectionKind} />
    </div>
  );
}

function ConnectionKindBadge({ kind }: { kind: CuratedConnectionKind }) {
  return <Badge variant="outline">{CONNECTION_KIND_LABELS[kind]}</Badge>;
}

function ConnectionStatusBadge({
  status,
}: {
  status: CuratedConnectionStatus;
}) {
  return (
    <Badge variant={connectionStatusVariant(status)}>
      {CONNECTION_STATUS_LABELS[status]}
    </Badge>
  );
}

function ConnectionExpiry({ value }: { value: string | null | undefined }) {
  const formatted = formatIntegrationDate(value, "No expiry");
  return <time dateTime={formatted.title}>{formatted.label}</time>;
}

function connectionName(connection: CuratedConnection | null): string {
  if (connection === null) return "this vendor";
  return (
    connection.displayName?.trim() ||
    formatIntegrationIdentifier(connection.vendor)
  );
}

function connectionStatusVariant(
  status: CuratedConnectionStatus,
): "default" | "destructive" | "outline" | "secondary" {
  if (status === "ACTIVE") return "secondary";
  if (status === "FAILED") return "destructive";
  return "outline";
}

function ConnectionsEmptyState({
  hasFilters,
  onClear,
  onOpenConfigured,
}: {
  hasFilters: boolean;
  onClear: () => void;
  onOpenConfigured: () => void;
}) {
  return (
    <div className="border py-16 text-center">
      <p className="text-sm font-medium">
        {hasFilters
          ? "No connections match these filters"
          : "No connections yet"}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        {hasFilters
          ? "Change or clear the filters to inspect other connections."
          : "Authorize an organization or end-user account from a configured integration."}
      </p>
      <Button
        className="mt-4"
        variant={hasFilters ? "outline" : "default"}
        onClick={hasFilters ? onClear : onOpenConfigured}
      >
        {hasFilters ? "Clear filters" : "View configured integrations"}
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
      <p className="text-sm font-medium">Connections are unavailable</p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      <Button className="mt-4" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function ConnectionLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-5 w-36 max-w-full" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-32 max-w-full" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20 max-w-full" />
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

function ConnectionLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-5 w-40 max-w-full" />
      <Skeleton className="h-4 w-28 max-w-full" />
      <Skeleton className="h-5 w-60 max-w-full" />
    </div>
  );
}

export { IntegrationConnectionsPage };
