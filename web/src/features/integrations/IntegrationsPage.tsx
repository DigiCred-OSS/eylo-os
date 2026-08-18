import { ArrowRight, Check, Search, SlidersHorizontal, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { CollectionToolbar } from "@/components/filters";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  applyIntegrationCatalogQuery,
  buildIntegrationCatalogSearchParams,
  parseIntegrationCatalogQuery,
} from "@/features/integrations/integrations.query";
import { INTEGRATION_AUTH_LABELS } from "@/features/integrations/integration-list-controls";
import type {
  CuratedAuthKind,
  CuratedVendor,
  IntegrationCatalogQuery,
} from "@/features/integrations/integrations.types";

const IntegrationsPage = observer(function IntegrationsPage() {
  const { integrations } = useRootStore();
  const { organizationId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          integrations.vendors.flatMap((vendor) => vendor.categories ?? []),
        ),
      ).sort((left, right) => left.localeCompare(right)),
    [integrations.vendors],
  );
  const paramsKey = searchParams.toString();
  const query = useMemo(
    () =>
      parseIntegrationCatalogQuery(new URLSearchParams(paramsKey), categories),
    [categories, paramsKey],
  );
  const visibleVendors = useMemo(
    () => applyIntegrationCatalogQuery(integrations.vendors, query),
    [integrations.vendors, query],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId) void integrations.loadCatalog(organizationId);
  }, [integrations, organizationId]);

  if (!organizationId) return null;
  const activeOrganizationId = organizationId;

  function updateQuery(patch: Partial<IntegrationCatalogQuery>): void {
    setSearchParams(
      buildIntegrationCatalogSearchParams({ ...query, ...patch }),
    );
  }

  function openVendor(vendor: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/integrations/${vendor}`,
      search: searchParams.toString(),
    });
  }

  const activeFilters = [
    query.category !== "all"
      ? {
          label: `Category: ${query.category}`,
          clear: () => updateQuery({ category: "all" }),
        }
      : null,
    query.auth !== "all"
      ? {
          label: `Auth: ${INTEGRATION_AUTH_LABELS[query.auth]}`,
          clear: () => updateQuery({ auth: "all" }),
        }
      : null,
    query.installed !== "all"
      ? {
          label:
            query.installed === "configured" ? "Configured" : "Not configured",
          clear: () => updateQuery({ installed: "all" }),
        }
      : null,
  ].filter(
    (item): item is { label: string; clear: () => void } => item !== null,
  );

  return (
    <section
      className="min-w-0 space-y-6 p-4 sm:p-6"
      aria-labelledby="integrations-title"
    >
      <header className="space-y-1">
        <h1
          id="integrations-title"
          className="text-2xl font-semibold tracking-tight"
        >
          Integrations
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Install a curated vendor, authorize an account, then choose the
          focused tools Agents may use.
        </p>
      </header>

      {integrations.catalogErrorMessage ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm"
          role="alert"
        >
          {integrations.catalogErrorMessage}
          <Button
            className="ml-3"
            size="sm"
            variant="outline"
            onClick={() => void integrations.loadCatalog(activeOrganizationId)}
          >
            Try again
          </Button>
        </div>
      ) : null}

      <CollectionToolbar
        listLabel="Integrations"
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
              aria-label="Search integrations"
              maxLength={100}
              placeholder="Search integrations"
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
          <CatalogFilterPopover
            categories={categories}
            query={query}
            onChange={updateQuery}
          />
        }
        sort={
          <Select
            value={query.sort}
            onValueChange={(value) =>
              updateQuery({ sort: value === "tools" ? "tools" : "name" })
            }
          >
            <SelectTrigger size="sm" aria-label="Sort integrations">
              <SelectValue>
                {query.sort === "tools" ? "Most tools" : "Name"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="name">Name</SelectItem>
              <SelectItem value="tools">Most tools</SelectItem>
            </SelectContent>
          </Select>
        }
        appliedFilters={
          activeFilters.length === 0 ? null : (
            <div
              className="flex flex-wrap gap-2"
              aria-label="Applied integration filters"
            >
              {activeFilters.map((filter) => (
                <Button
                  key={filter.label}
                  size="sm"
                  variant="secondary"
                  onClick={filter.clear}
                >
                  {filter.label}
                  <X aria-hidden="true" />
                </Button>
              ))}
            </div>
          )
        }
      />

      {integrations.isCatalogLoading && integrations.vendors.length === 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 9 }, (_, index) => (
            <VendorSkeleton key={index} />
          ))}
        </div>
      ) : visibleVendors.length === 0 ? (
        <div className="border py-16 text-center">
          <p className="text-sm font-medium">No integrations match</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Clear a filter or try another search.
          </p>
        </div>
      ) : (
        <div
          className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
          role="list"
          aria-label="Integration catalog"
        >
          {visibleVendors.map((vendor) => (
            <VendorCard
              key={vendor.vendor}
              vendor={vendor}
              onOpen={() => openVendor(vendor.vendor)}
            />
          ))}
        </div>
      )}
    </section>
  );
});

function CatalogFilterPopover({
  categories,
  onChange,
  query,
}: {
  categories: string[];
  onChange: (patch: Partial<IntegrationCatalogQuery>) => void;
  query: IntegrationCatalogQuery;
}) {
  return (
    <Popover>
      <PopoverTrigger render={<Button size="sm" variant="outline" />}>
        <SlidersHorizontal aria-hidden="true" />
        Filter
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-3">
        <PopoverHeader>
          <PopoverTitle>Filter integrations</PopoverTitle>
        </PopoverHeader>
        <CatalogSelect
          label="Configuration"
          value={query.installed}
          onValueChange={(value) =>
            onChange({
              installed:
                value === "configured" || value === "available" ? value : "all",
            })
          }
          options={[
            ["all", "All"],
            ["configured", "Configured"],
            ["available", "Not configured"],
          ]}
        />
        <CatalogSelect
          label="Authorization"
          value={query.auth}
          onValueChange={(value) =>
            onChange({
              auth: value === "all" ? "all" : (value as CuratedAuthKind),
            })
          }
          options={[
            ["all", "All methods"],
            ...Object.entries(INTEGRATION_AUTH_LABELS),
          ]}
        />
        <CatalogSelect
          label="Category"
          value={query.category}
          onValueChange={(value) => onChange({ category: value ?? "all" })}
          options={[
            ["all", "All categories"],
            ...categories.map(
              (category) => [category, category] as [string, string],
            ),
          ]}
        />
      </PopoverContent>
    </Popover>
  );
}

function CatalogSelect({
  label,
  onValueChange,
  options,
  value,
}: {
  label: string;
  onValueChange: (value: string | null) => void;
  options: [string, string][];
  value: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-full" aria-label={label}>
          <SelectValue>
            {options.find(([option]) => option === value)?.[1]}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {options.map(([option, text]) => (
            <SelectItem key={option} value={option}>
              {text}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function VendorCard({
  onOpen,
  vendor,
}: {
  onOpen: () => void;
  vendor: CuratedVendor;
}) {
  return (
    <article className="flex min-w-0 flex-col gap-4 border p-4" role="listitem">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="break-words font-medium">{vendor.displayName}</h2>
          <p className="mt-1 line-clamp-3 text-sm leading-6 text-muted-foreground">
            {vendor.description}
          </p>
        </div>
        {vendor.installed ? (
          <Badge variant="secondary">
            <Check aria-hidden="true" />
            Configured
          </Badge>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {(vendor.categories ?? []).slice(0, 3).map((category) => (
          <Badge key={category} variant="outline">
            {category}
          </Badge>
        ))}
      </div>
      <div className="mt-auto flex items-end justify-between gap-3 border-t pt-3">
        <div className="min-w-0 text-xs leading-5 text-muted-foreground">
          <p>
            {vendor.toolCount} curated tool{vendor.toolCount === 1 ? "" : "s"}
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {(vendor.authKinds ?? []).map((kind) => (
              <Badge key={kind} variant="outline">
                {INTEGRATION_AUTH_LABELS[kind]}
              </Badge>
            ))}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Open ${vendor.displayName}`}
          title={`Open ${vendor.displayName}`}
          onClick={onOpen}
        >
          <ArrowRight aria-hidden="true" />
        </Button>
      </div>
    </article>
  );
}

function VendorSkeleton() {
  return (
    <div className="space-y-4 border p-4">
      <Skeleton className="h-5 w-36" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-8 w-48 max-w-full" />
    </div>
  );
}

export { IntegrationsPage };
