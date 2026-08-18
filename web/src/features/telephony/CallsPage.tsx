import { Ellipsis, Eye, Search } from "lucide-react";
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
import { CallDetailsDrawer } from "@/features/telephony/CallDetailsDrawer";
import {
  formatCallDuration,
  formatTelephonyDate,
  formatTelephonyEnum,
} from "@/features/telephony/telephony-formatters";
import {
  CALL_FILTER_SCHEMA,
  CALL_SORT_OPTIONS,
} from "@/features/telephony/telephony-list-controls";
import {
  applyCallQuery,
  buildCallSearchParams,
  DEFAULT_CALL_QUERY,
  hasCallFilters,
  parseCallQuery,
} from "@/features/telephony/telephony.query";
import type {
  CallCollectionQuery,
  CallSortField,
  TelephonyCall,
} from "@/features/telephony/telephony.types";

const CallsPage = observer(function CallsPage() {
  const { telephony } = useRootStore();
  const store = telephony.calls;
  const { callId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchKey = searchParams.toString();
  const query = useMemo(
    () => parseCallQuery(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const visible = useMemo(
    () => applyCallQuery(store.items, query, CALL_FILTER_SCHEMA),
    [query, store.items],
  );

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId === undefined) return;
    void store.loadCollection();
    void telephony.loadReferences(organizationId);
  }, [organizationId, store, telephony]);
  useEffect(() => {
    if (callId !== undefined) void store.loadSelected(callId);
    else store.clearSelected();
    return store.clearSelected;
  }, [callId, store]);

  if (organizationId === undefined) return null;
  const basePath = `/org/${organizationId}/telephony/calls`;
  function setQuery(next: CallCollectionQuery): void {
    setSearchParams(buildCallSearchParams(next));
  }
  function updateQuery(patch: Partial<CallCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }
  function open(id: string): void {
    void navigate({ pathname: `${basePath}/${id}`, search: location.search });
  }
  function close(): void {
    void navigate({ pathname: basePath, search: location.search });
  }
  function sortBy(field: CallSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field === "provider" || field === "status"
            ? "asc"
            : "desc",
      sortBy: field,
    });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="calls-title">
      <header className="space-y-1">
        <h1 id="calls-title" className="text-2xl font-semibold tracking-tight">
          Calls
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Review inbound and outbound carrier calls, canonical lifecycle, exact
          Agent authority, conversations, voice sessions, and transfers.
        </p>
      </header>
      <CollectionToolbar
        listLabel="Calls"
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
              aria-label="Search calls"
              maxLength={100}
              placeholder="Search numbers, provider, or call ID"
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
            listLabel="Calls"
            schema={CALL_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Calls"
            options={CALL_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Calls"
            schema={CALL_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />
      <CallsTable
        agentName={telephony.agentName}
        errorMessage={store.collectionErrorMessage}
        hasActiveFilters={hasCallFilters(query)}
        isLoading={store.isCollectionLoading}
        items={visible}
        onClear={() =>
          setQuery({
            ...query,
            filters: DEFAULT_CALL_QUERY.filters,
            search: "",
          })
        }
        onRetry={() => void store.loadCollection()}
        onView={open}
      />
      <CallDetailsDrawer
        callId={callId}
        onClose={close}
        organizationId={organizationId}
      />
    </section>
  );
});

function CallsTable({
  agentName,
  errorMessage,
  hasActiveFilters,
  isLoading,
  items,
  onClear,
  onRetry,
  onView,
}: {
  agentName: (id: string | null | undefined) => string;
  errorMessage: string | null;
  hasActiveFilters: boolean;
  isLoading: boolean;
  items: readonly TelephonyCall[];
  onClear: () => void;
  onRetry: () => void;
  onView: (id: string) => void;
}) {
  if (errorMessage !== null)
    return (
      <Empty
        action="Try again"
        description={errorMessage}
        onAction={onRetry}
        title="Calls are unavailable"
      />
    );
  if (!isLoading && items.length === 0)
    return (
      <Empty
        action={hasActiveFilters ? "Clear filters" : undefined}
        description={
          hasActiveFilters
            ? "Change or clear the filters to inspect other calls."
            : "Carrier calls appear here after an inbound or outbound telephony flow starts."
        }
        onAction={onClear}
        title={
          hasActiveFilters ? "No calls match these filters" : "No calls yet"
        }
      />
    );
  return (
    <div className="border">
      <div className="divide-y sm:hidden" role="list" aria-label="Calls">
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => <LoadingCard key={index} />)
          : items.map((call) => (
              <CallCard
                agentName={agentName(call.agentId)}
                call={call}
                key={call.id}
                onView={onView}
              />
            ))}
      </div>
      <Table className="hidden table-fixed sm:table" aria-label="Calls">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[29%]">Call</TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="hidden w-28 md:table-cell">
              Direction
            </TableHead>
            <TableHead className="hidden w-[19%] lg:table-cell">
              Agent
            </TableHead>
            <TableHead className="hidden w-28 xl:table-cell">
              Duration
            </TableHead>
            <TableHead className="w-44">Started</TableHead>
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
            : items.map((call) => (
                <CallRow
                  agentName={agentName(call.agentId)}
                  call={call}
                  key={call.id}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading calls…"
          : `${items.length} call${items.length === 1 ? "" : "s"} · most recent 100`}
      </div>
    </div>
  );
}

function CallRow({
  agentName,
  call,
  onView,
}: {
  agentName: string;
  call: TelephonyCall;
  onView: (id: string) => void;
}) {
  const started = formatTelephonyDate(call.startedAt);
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(call.id)}
        >
          {call.fromNumber ?? "Unknown"} → {call.toNumber ?? "Unknown"}
        </button>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {formatTelephonyEnum(call.provider)} · …{call.id.slice(-8)}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant={call.status === "failed" ? "destructive" : "outline"}>
          {formatTelephonyEnum(call.status)}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">{formatTelephonyEnum(call.direction)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal lg:table-cell">
        {agentName}
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        {formatCallDuration(call.durationSeconds)}
      </TableCell>
      <TableCell className="whitespace-normal">
        {call.startedAt === null || call.startedAt === undefined ? (
          started.label
        ) : (
          <time dateTime={call.startedAt} title={started.title}>
            {started.label}
          </time>
        )}
      </TableCell>
      <TableCell className="text-right">
        <CallMenu call={call} onView={onView} />
      </TableCell>
    </TableRow>
  );
}
function CallCard({
  agentName,
  call,
  onView,
}: {
  agentName: string;
  call: TelephonyCall;
  onView: (id: string) => void;
}) {
  const started = formatTelephonyDate(call.startedAt);
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <button
          className="text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(call.id)}
        >
          {call.fromNumber ?? "Unknown"} → {call.toNumber ?? "Unknown"}
        </button>
        <CallMenu call={call} onView={onView} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant={call.status === "failed" ? "destructive" : "outline"}>
          {formatTelephonyEnum(call.status)}
        </Badge>
        <Badge variant="outline">{formatTelephonyEnum(call.direction)}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        {agentName} · {formatCallDuration(call.durationSeconds)} ·{" "}
        {started.label}
      </p>
    </article>
  );
}
function CallMenu({
  call,
  onView,
}: {
  call: TelephonyCall;
  onView: (id: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for call ${call.id}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(call.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
function LoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-4 w-20" />
      </TableCell>
      <TableCell>
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
      <Skeleton className="h-3 w-48" />
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

export { CallsPage };
