import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  ArrowUpDown,
  Eye,
  Plus,
  Search,
} from "lucide-react";
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
import { ProviderConfigActions } from "@/features/providers/ProviderConfigActions";
import { ProviderDetailsDrawer } from "@/features/providers/ProviderDetailsDrawer";
import { ProviderStatusBadge } from "@/features/providers/ProviderStatusBadge";
import { ProviderToolsSection } from "@/features/providers/ProviderToolsSection";
import {
  createProviderFilterSchema,
  PROVIDER_SORT_OPTIONS,
} from "@/features/providers/provider-list-controls";
import {
  formatProviderDate,
  formatProviderIdentifier,
} from "@/features/providers/provider-formatters";
import {
  preserveReturnContext,
  providerCollectionPath,
  safeOrganizationReturnPath,
} from "@/features/providers/provider-navigation";
import {
  applyProviderCollectionQuery,
  buildProviderCollectionSearchParams,
  hasProviderCollectionFilters,
  parseProviderCollectionQuery,
} from "@/features/providers/providers.query";
import {
  PROVIDER_CAPABILITIES,
  type ProviderCapability,
  type ProviderCollectionQuery,
  type ProviderConfigRecord,
  type ProviderSortField,
} from "@/features/providers/providers.types";

const ProviderConfigsPage = observer(function ProviderConfigsPage() {
  const { auth, providers } = useRootStore();
  const member = auth.member;
  const { capability: capabilityParam, configId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const capability = parseCapability(capabilityParam);
  const definition =
    capability === null ? null : providers.definitionFor(capability);
  const providerIds = useMemo(
    () => definition?.providers.map((provider) => provider.id) ?? [],
    [definition],
  );
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () =>
      parseProviderCollectionQuery(
        new URLSearchParams(searchParamsKey),
        providerIds,
      ),
    [providerIds, searchParamsKey],
  );
  const filterSchema = useMemo(
    () => (definition === null ? null : createProviderFilterSchema(definition)),
    [definition],
  );
  const visibleItems = useMemo(
    () =>
      filterSchema === null
        ? providers.items
        : applyProviderCollectionQuery(providers.items, query, filterSchema),
    [filterSchema, providers.items, query],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const returnTo = safeOrganizationReturnPath(
    searchParams.get("returnTo"),
    organizationId,
  );

  useEffect(() => {
    setSearchDraft(query.search);
  }, [query.search]);

  useEffect(() => {
    if (capability !== null) {
      void providers.loadCapability(capability);
      if (organizationId !== undefined) {
        void providers.loadProviderTools(organizationId, capability);
      }
    }
  }, [capability, organizationId, providers]);

  useEffect(() => {
    if (capability !== null && configId !== undefined) {
      void providers.loadSelected(capability, configId);
    } else {
      providers.clearSelected();
    }
    return providers.clearSelected;
  }, [capability, configId, providers]);

  if (organizationId === undefined) {
    return null;
  }
  if (capability === null) {
    return (
      <section className="p-6" role="alert">
        <p className="text-sm font-medium">Unknown provider capability</p>
        <Button
          className="mt-4"
          variant="outline"
          onClick={() =>
            void navigate(returnTo ?? `/org/${organizationId}/providers`)
          }
        >
          Back to Providers
        </Button>
      </section>
    );
  }
  const activeOrganizationId: string = organizationId;
  const activeCapability: ProviderCapability = capability;

  function setQuery(nextQuery: ProviderCollectionQuery): void {
    setSearchParams(
      preserveReturnContext(
        buildProviderCollectionSearchParams(nextQuery, providerIds),
        searchParams,
        activeOrganizationId,
      ),
    );
  }

  function updateQuery(patch: Partial<ProviderCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function collectionPath(): string {
    return providerCollectionPath(activeOrganizationId, activeCapability);
  }

  function leaveCapability(): void {
    void navigate(returnTo ?? `/org/${activeOrganizationId}/providers`);
  }

  function openConfig(nextConfigId: string): void {
    void navigate({
      pathname: `${collectionPath()}/${nextConfigId}`,
      search: location.search,
    });
  }

  function closeConfig(): void {
    void navigate({ pathname: collectionPath(), search: location.search });
  }

  function editConfig(nextConfigId: string): void {
    void navigate({
      pathname: `${collectionPath()}/${nextConfigId}/edit`,
      search: location.search,
    });
  }

  function createConfig(): void {
    if (definition === null || member === null) {
      return;
    }
    providers.form.startNew(
      {
        capability: activeCapability,
        memberKey: member.email,
        organizationId: activeOrganizationId,
      },
      definition,
    );
    void navigate({
      pathname: `${collectionPath()}/new`,
      search: location.search,
    });
  }

  function providerLabelFor(config: ProviderConfigRecord): string {
    return (
      definition?.providers.find((provider) => provider.id === config.provider)
        ?.label ?? formatProviderIdentifier(config.provider)
    );
  }

  function sortBy(field: ProviderSortField): void {
    const direction =
      query.sortBy === field
        ? query.direction === "asc"
          ? "desc"
          : "asc"
        : field === "verified_at"
          ? "desc"
          : "asc";
    updateQuery({ direction, sortBy: field });
  }

  const title = definition?.label ?? formatProviderIdentifier(capability);
  const hasFilters = hasProviderCollectionFilters(query);

  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="provider-configs-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to Providers"
            title="Back to Providers"
            onClick={leaveCapability}
          >
            <ArrowLeft aria-hidden="true" />
          </Button>
          <div className="space-y-1">
            <h1
              id="provider-configs-title"
              className="text-2xl font-semibold tracking-tight"
            >
              {title}
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              {definition?.description ?? "Configure this provider capability."}
            </p>
          </div>
        </div>
        <Button
          onClick={createConfig}
          disabled={definition === null || member === null}
        >
          <Plus aria-hidden="true" />
          New configuration
        </Button>
      </header>

      <ProviderToolsSection
        errorMessage={providers.providerToolsErrorMessage}
        isLoading={providers.isProviderToolsLoading}
        isStale={providers.isProviderToolsStale}
        tools={providers.providerTools}
        onRetry={() =>
          void providers.loadProviderTools(
            activeOrganizationId,
            activeCapability,
          )
        }
      />

      {providers.isCollectionStale ? (
        <div
          className="border border-warning/40 bg-warning/10 p-3 text-sm"
          role="alert"
        >
          Showing the last loaded configurations.{" "}
          {providers.collectionErrorMessage}
        </div>
      ) : null}

      {filterSchema === null ? null : (
        <CollectionToolbar
          listLabel={`${title} configurations`}
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
                aria-label={`Search ${title} configurations`}
                maxLength={100}
                placeholder="Search configurations"
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
              listLabel={`${title} configurations`}
              schema={filterSchema}
              onChange={(filters) => updateQuery({ filters })}
            />
          }
          sort={
            <SortControl
              direction={query.direction}
              listLabel={`${title} configurations`}
              options={PROVIDER_SORT_OPTIONS}
              sort={query.sortBy}
              onDirectionChange={(direction) => updateQuery({ direction })}
              onSortChange={(sortBy) =>
                updateQuery({
                  direction: sortBy === "verified_at" ? "desc" : "asc",
                  sortBy,
                })
              }
            />
          }
          appliedFilters={
            <AppliedFilterBar
              filterTree={query.filters}
              listLabel={`${title} configurations`}
              schema={filterSchema}
              onChange={(filters) => updateQuery({ filters })}
            />
          }
        />
      )}

      {providers.collectionErrorMessage !== null &&
      providers.items.length === 0 ? (
        <div className="border py-16 text-center" role="alert">
          <p className="text-sm font-medium">Configurations are unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {providers.collectionErrorMessage}
          </p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => void providers.loadCapability(capability)}
          >
            Try again
          </Button>
        </div>
      ) : !providers.isCollectionLoading && visibleItems.length === 0 ? (
        <div className="border py-16 text-center">
          <p className="text-sm font-medium">
            {hasFilters
              ? "No configurations match these filters"
              : `No ${title} configurations yet`}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {hasFilters
              ? "Change or clear the filters to see other configurations."
              : "Create and save a configuration, then verify it explicitly."}
          </p>
          {hasFilters ? (
            <Button
              className="mt-4"
              variant="outline"
              onClick={() =>
                setQuery({
                  direction: "asc",
                  filters: { ...query.filters, children: [] },
                  search: "",
                  sortBy: "name",
                })
              }
            >
              Clear filters
            </Button>
          ) : (
            <Button
              className="mt-4"
              onClick={createConfig}
              disabled={definition === null || member === null}
            >
              <Plus aria-hidden="true" />
              New configuration
            </Button>
          )}
        </div>
      ) : (
        <div className="border">
          <div
            className="divide-y sm:hidden"
            role="list"
            aria-label={`${title} configurations`}
          >
            {providers.isCollectionLoading && providers.items.length === 0
              ? Array.from({ length: 6 }, (_, index) => (
                  <ConfigLoadingCard key={index} />
                ))
              : visibleItems.map((config) => (
                  <ConfigCard
                    key={config.id}
                    config={config}
                    providerLabel={providerLabelFor(config)}
                    onDeleted={() => {
                      if (configId === config.id) {
                        closeConfig();
                      }
                    }}
                    onEdit={editConfig}
                    onView={openConfig}
                  />
                ))}
          </div>

          <Table
            className="hidden sm:table"
            aria-label={`${title} configurations`}
          >
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <SortableHead
                  field="name"
                  label="Name"
                  query={query}
                  onSort={sortBy}
                />
                <SortableHead
                  field="provider"
                  label="Provider"
                  query={query}
                  onSort={sortBy}
                />
                <SortableHead
                  field="ready"
                  label="Status"
                  query={query}
                  onSort={sortBy}
                />
                <TableHead className="hidden md:table-cell">Revision</TableHead>
                <SortableHead
                  className="hidden lg:table-cell"
                  field="verified_at"
                  label="Verified"
                  query={query}
                  onSort={sortBy}
                />
                <TableHead className="w-12 text-right">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.isCollectionLoading && providers.items.length === 0
                ? Array.from({ length: 6 }, (_, index) => (
                    <ConfigLoadingRow key={index} />
                  ))
                : visibleItems.map((config) => (
                    <ConfigRow
                      key={config.id}
                      config={config}
                      providerLabel={providerLabelFor(config)}
                      onDeleted={() => {
                        if (configId === config.id) {
                          closeConfig();
                        }
                      }}
                      onEdit={editConfig}
                      onView={openConfig}
                    />
                  ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ProviderDetailsDrawer
        configId={configId}
        onClose={closeConfig}
        onEdit={editConfig}
      />
    </section>
  );
});

function ConfigRow({
  config,
  onDeleted,
  onEdit,
  onView,
  providerLabel,
}: {
  config: ProviderConfigRecord;
  onDeleted: () => void;
  onEdit: (configId: string) => void;
  onView: (configId: string) => void;
  providerLabel: string;
}) {
  const verifiedAt = formatProviderDate(config.verifiedAt);
  return (
    <TableRow>
      <TableCell className="max-w-64 whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(config.id)}
        >
          {config.name}
        </button>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {config.id}
        </p>
      </TableCell>
      <TableCell>{providerLabel}</TableCell>
      <TableCell>
        <ProviderStatusBadge
          configured={config.configured}
          enabled={config.enabled}
          ready={config.ready}
          verified={config.verified}
        />
      </TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">
        {config.revision}
      </TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">
        {verifiedAt.exact === null ? (
          verifiedAt.label
        ) : (
          <time dateTime={verifiedAt.exact} title={`${verifiedAt.exact} (UTC)`}>
            {verifiedAt.label}
          </time>
        )}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="icon"
            aria-label={`View ${config.name}`}
            title={`View ${config.name}`}
            onClick={() => onView(config.id)}
          >
            <Eye aria-hidden="true" />
          </Button>
          <ProviderConfigActions
            config={config}
            onDeleted={onDeleted}
            onEdit={() => onEdit(config.id)}
          />
        </div>
      </TableCell>
    </TableRow>
  );
}

function ConfigCard({
  config,
  onDeleted,
  onEdit,
  onView,
  providerLabel,
}: {
  config: ProviderConfigRecord;
  onDeleted: () => void;
  onEdit: (configId: string) => void;
  onView: (configId: string) => void;
  providerLabel: string;
}) {
  const verifiedAt = formatProviderDate(config.verifiedAt);
  const verificationLabel =
    verifiedAt.exact === null
      ? verifiedAt.label
      : `Verified ${verifiedAt.label.toLowerCase()}`;
  return (
    <div className="space-y-3 p-4" role="listitem">
      <div className="flex items-start gap-2">
        <button
          className="min-w-0 flex-1 text-left focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(config.id)}
        >
          <span className="block font-medium">{config.name}</span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {config.id}
          </span>
        </button>
        <div className="flex shrink-0">
          <Button
            variant="ghost"
            size="icon"
            aria-label={`View ${config.name}`}
            title={`View ${config.name}`}
            onClick={() => onView(config.id)}
          >
            <Eye aria-hidden="true" />
          </Button>
          <ProviderConfigActions
            config={config}
            onDeleted={onDeleted}
            onEdit={() => onEdit(config.id)}
          />
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{providerLabel}</p>
      <ProviderStatusBadge
        configured={config.configured}
        enabled={config.enabled}
        ready={config.ready}
        verified={config.verified}
      />
      <p className="text-xs text-muted-foreground">
        Revision {config.revision} · {verificationLabel}
      </p>
    </div>
  );
}

function SortableHead({
  className,
  field,
  label,
  onSort,
  query,
}: {
  className?: string;
  field: ProviderSortField;
  label: string;
  onSort: (field: ProviderSortField) => void;
  query: ProviderCollectionQuery;
}) {
  const Icon =
    query.sortBy !== field
      ? ArrowUpDown
      : query.direction === "asc"
        ? ArrowUp
        : ArrowDown;
  return (
    <TableHead className={className} aria-sort={sortAriaValue(query, field)}>
      <button
        className="flex items-center gap-1 rounded-sm underline-offset-4 hover:underline focus-visible:outline-2"
        type="button"
        onClick={() => onSort(field)}
      >
        {label}
        <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
      </button>
    </TableHead>
  );
}

function sortAriaValue(
  query: ProviderCollectionQuery,
  field: ProviderSortField,
): "ascending" | "descending" | "none" {
  return query.sortBy !== field
    ? "none"
    : query.direction === "asc"
      ? "ascending"
      : "descending";
}

function ConfigLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-5 w-36" />
        <Skeleton className="mt-2 h-3 w-52" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-6 w-64 max-w-full" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-8" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function ConfigLoadingCard() {
  return (
    <div className="space-y-3 p-4" role="listitem">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <Skeleton className="h-5 w-36 max-w-full" />
          <Skeleton className="mt-2 h-3 w-52 max-w-full" />
        </div>
        <Skeleton className="size-8 shrink-0" />
      </div>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-6 w-64 max-w-full" />
      <Skeleton className="h-3 w-40" />
    </div>
  );
}

function parseCapability(value: string | undefined): ProviderCapability | null {
  return PROVIDER_CAPABILITIES.includes(value as ProviderCapability)
    ? (value as ProviderCapability)
    : null;
}

export { ProviderConfigsPage };
