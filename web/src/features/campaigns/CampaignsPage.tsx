import { Ellipsis, Eye, Pencil, Plus, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import {
  Link,
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
import { CampaignDetailsDrawer } from "@/features/campaigns/CampaignDetailsDrawer";
import {
  campaignProgress,
  formatCampaignDate,
  formatCampaignEnum,
} from "@/features/campaigns/campaign-formatters";
import {
  CAMPAIGN_FILTER_SCHEMA,
  CAMPAIGN_SORT_OPTIONS,
} from "@/features/campaigns/campaigns-list-controls";
import {
  applyCampaignQuery,
  buildCampaignSearchParams,
  DEFAULT_CAMPAIGN_QUERY,
  hasCampaignFilters,
  parseCampaignQuery,
} from "@/features/campaigns/campaigns.query";
import type {
  Campaign,
  CampaignCollectionQuery,
  CampaignSortField,
} from "@/features/campaigns/campaigns.types";

const CampaignsPage = observer(function CampaignsPage() {
  const { campaigns } = useRootStore();
  const { campaignId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchKey = searchParams.toString();
  const query = useMemo(
    () => parseCampaignQuery(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const visible = useMemo(
    () => applyCampaignQuery(campaigns.items, query, CAMPAIGN_FILTER_SCHEMA),
    [campaigns.items, query],
  );

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId === undefined) return;
    void campaigns.loadCollection(organizationId);
    void campaigns.loadReferences(organizationId);
  }, [campaigns, organizationId]);
  useEffect(() => {
    if (organizationId !== undefined && campaignId !== undefined)
      void campaigns.loadSelected(organizationId, campaignId);
    else campaigns.clearSelected();
    return campaigns.clearSelected;
  }, [campaignId, campaigns, organizationId]);

  if (organizationId === undefined) return null;
  const basePath = `/org/${organizationId}/outbound/campaigns`;
  function setQuery(next: CampaignCollectionQuery): void {
    setSearchParams(buildCampaignSearchParams(next));
  }
  function updateQuery(patch: Partial<CampaignCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }
  function open(id: string): void {
    void navigate({ pathname: `${basePath}/${id}`, search: location.search });
  }
  function close(): void {
    void navigate({ pathname: basePath, search: location.search });
  }
  function sortBy(field: CampaignSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field === "name" || field === "status"
            ? "asc"
            : "desc",
      sortBy: field,
    });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="campaigns-title">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="campaigns-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Outbound campaigns
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Reach a defined audience through voice, email, or widget
            conversations with pinned Agent authority, durable attempts, and
            explicit preparation warnings.
          </p>
        </div>
        <Button nativeButton={false} render={<Link to={`${basePath}/new`} />}>
          <Plus aria-hidden="true" />
          New campaign
        </Button>
      </header>
      <CollectionToolbar
        listLabel="Campaigns"
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
              aria-label="Search campaigns"
              maxLength={100}
              placeholder="Search campaign name or description"
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
            listLabel="Campaigns"
            schema={CAMPAIGN_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Campaigns"
            options={CAMPAIGN_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Campaigns"
            schema={CAMPAIGN_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />
      <CampaignsTable
        agentName={campaigns.agentName}
        errorMessage={campaigns.collectionErrorMessage}
        hasActiveFilters={hasCampaignFilters(query)}
        isLoading={campaigns.isCollectionLoading}
        items={visible}
        onClear={() =>
          setQuery({
            ...query,
            filters: DEFAULT_CAMPAIGN_QUERY.filters,
            search: "",
          })
        }
        onRetry={() => void campaigns.loadCollection(organizationId)}
        onView={open}
        organizationId={organizationId}
      />
      <CampaignDetailsDrawer
        campaignId={campaignId}
        onClose={close}
        organizationId={organizationId}
      />
    </section>
  );
});

function CampaignsTable({
  agentName,
  errorMessage,
  hasActiveFilters,
  isLoading,
  items,
  onClear,
  onRetry,
  onView,
  organizationId,
}: {
  agentName: (id: string) => string;
  errorMessage: string | null;
  hasActiveFilters: boolean;
  isLoading: boolean;
  items: readonly Campaign[];
  onClear: () => void;
  onRetry: () => void;
  onView: (id: string) => void;
  organizationId: string;
}) {
  if (errorMessage !== null)
    return (
      <Empty
        action="Try again"
        description={errorMessage}
        onAction={onRetry}
        title="Campaigns are unavailable"
      />
    );
  if (!isLoading && items.length === 0)
    return (
      <Empty
        action={hasActiveFilters ? "Clear filters" : undefined}
        description={
          hasActiveFilters
            ? "Change or clear the filters to inspect other campaigns."
            : "Create a campaign, add recipients, review preparation warnings, then start it explicitly."
        }
        onAction={onClear}
        title={
          hasActiveFilters
            ? "No campaigns match these filters"
            : "No campaigns yet"
        }
      />
    );
  return (
    <div className="border">
      <div className="divide-y sm:hidden" role="list" aria-label="Campaigns">
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => <LoadingCard key={index} />)
          : items.map((campaign) => (
              <CampaignCard
                agentName={agentName(campaign.agentId)}
                campaign={campaign}
                key={campaign.id}
                onView={onView}
                organizationId={organizationId}
              />
            ))}
      </div>
      <Table className="hidden table-fixed sm:table" aria-label="Campaigns">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[29%]">Campaign</TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="hidden w-24 md:table-cell">Channel</TableHead>
            <TableHead className="hidden w-[18%] lg:table-cell">
              Agent
            </TableHead>
            <TableHead className="w-[19%]">Progress</TableHead>
            <TableHead className="hidden w-40 xl:table-cell">Updated</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <LoadingRow key={index} />
              ))
            : items.map((campaign) => (
                <CampaignRow
                  agentName={agentName(campaign.agentId)}
                  campaign={campaign}
                  key={campaign.id}
                  onView={onView}
                  organizationId={organizationId}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading campaigns…"
          : `${items.length} campaign${items.length === 1 ? "" : "s"} · first 100`}
      </div>
    </div>
  );
}

function CampaignRow({
  agentName,
  campaign,
  onView,
  organizationId,
}: {
  agentName: string;
  campaign: Campaign;
  onView: (id: string) => void;
  organizationId: string;
}) {
  const progress = campaignProgress(
    campaign.completedContacts,
    campaign.failedContacts,
    campaign.totalContacts,
  );
  const updated = formatCampaignDate(campaign.updatedAt);
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <button
          className="line-clamp-2 text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(campaign.id)}
        >
          {campaign.name}
        </button>
        <p className="mt-0.5 text-xs text-muted-foreground">
          revision {campaign.publishedRevision}
        </p>
      </TableCell>
      <TableCell>
        <Badge
          variant={campaign.status === "canceled" ? "destructive" : "outline"}
        >
          {formatCampaignEnum(campaign.status)}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">{formatCampaignEnum(campaign.channel)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal lg:table-cell">
        {agentName}
      </TableCell>
      <TableCell className="whitespace-normal">
        <div className="space-y-1">
          <div className="h-1.5 overflow-hidden bg-muted">
            <div
              className="h-full bg-foreground"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">{progress.label}</p>
        </div>
      </TableCell>
      <TableCell className="hidden whitespace-normal xl:table-cell">
        <time dateTime={campaign.updatedAt} title={updated.title}>
          {updated.label}
        </time>
      </TableCell>
      <TableCell className="text-right">
        <CampaignMenu
          campaign={campaign}
          onView={onView}
          organizationId={organizationId}
        />
      </TableCell>
    </TableRow>
  );
}
function CampaignCard({
  agentName,
  campaign,
  onView,
  organizationId,
}: {
  agentName: string;
  campaign: Campaign;
  onView: (id: string) => void;
  organizationId: string;
}) {
  const progress = campaignProgress(
    campaign.completedContacts,
    campaign.failedContacts,
    campaign.totalContacts,
  );
  const updated = formatCampaignDate(campaign.updatedAt);
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <button
          className="line-clamp-2 text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(campaign.id)}
        >
          {campaign.name}
        </button>
        <CampaignMenu
          campaign={campaign}
          onView={onView}
          organizationId={organizationId}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge
          variant={campaign.status === "canceled" ? "destructive" : "outline"}
        >
          {formatCampaignEnum(campaign.status)}
        </Badge>
        <Badge variant="outline">{formatCampaignEnum(campaign.channel)}</Badge>
      </div>
      <div className="h-1.5 overflow-hidden bg-muted">
        <div
          className="h-full bg-foreground"
          style={{ width: `${progress.percent}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {agentName} · {progress.label} · {updated.label}
      </p>
    </article>
  );
}
function CampaignMenu({
  campaign,
  onView,
  organizationId,
}: {
  campaign: Campaign;
  onView: (id: string) => void;
  organizationId: string;
}) {
  const editable = campaign.status === "draft" || campaign.status === "paused";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${campaign.name}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(campaign.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
        {editable ? (
          <DropdownMenuItem
            render={
              <Link
                to={`/org/${organizationId}/outbound/campaigns/${campaign.id}/edit`}
              />
            }
          >
            <Pencil aria-hidden="true" />
            Edit
          </DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
function LoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-3 w-20" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-6 w-full" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}
function LoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-5 w-36" />
      <Skeleton className="h-3 w-52" />
    </div>
  );
}
function Empty({
  action,
  description,
  onAction,
  title,
}: {
  action?: string;
  description: string;
  onAction: () => void;
  title: string;
}) {
  return (
    <div className="border py-16 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-lg text-sm text-muted-foreground">
        {description}
      </p>
      {action === undefined ? null : (
        <Button className="mt-4" variant="outline" onClick={onAction}>
          {action}
        </Button>
      )}
    </div>
  );
}

export { CampaignsPage };
