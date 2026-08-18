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
import {
  formatDuration,
  formatOperationDate,
  formatOperationEnum,
} from "@/features/operations/operation-formatters";
import {
  VOICE_SESSION_FILTER_SCHEMA,
  VOICE_SESSION_SORT_OPTIONS,
} from "@/features/operations/operations-list-controls";
import {
  applyVoiceSessionQuery,
  buildVoiceSessionSearchParams,
  DEFAULT_VOICE_SESSION_QUERY,
  hasFilters,
  parseVoiceSessionQuery,
} from "@/features/operations/operations.query";
import type {
  VoiceSession,
  VoiceSessionCollectionQuery,
  VoiceSessionSortField,
} from "@/features/operations/operations.types";
import { VoiceSessionDetailsDrawer } from "@/features/operations/VoiceSessionDetailsDrawer";

const VoiceSessionsPage = observer(function VoiceSessionsPage() {
  const { operations } = useRootStore();
  const store = operations.voiceSessions;
  const { organizationId, voiceSessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchKey = searchParams.toString();
  const query = useMemo(
    () => parseVoiceSessionQuery(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const visible = useMemo(
    () =>
      applyVoiceSessionQuery(store.items, query, VOICE_SESSION_FILTER_SCHEMA),
    [query, store.items],
  );
  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined) {
      void store.loadCollection(organizationId);
      void operations.loadAgentReferences(organizationId);
    }
  }, [operations, organizationId, store]);
  useEffect(() => {
    if (organizationId !== undefined && voiceSessionId !== undefined)
      void store.loadSelected(organizationId, voiceSessionId);
    else store.clearSelected();
    return store.clearSelected;
  }, [organizationId, store, voiceSessionId]);
  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;
  function setQuery(next: VoiceSessionCollectionQuery): void {
    setSearchParams(buildVoiceSessionSearchParams(next));
  }
  function updateQuery(patch: Partial<VoiceSessionCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }
  function open(id: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/voice-sessions/${id}`,
      search: location.search,
    });
  }
  function close(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/voice-sessions`,
      search: location.search,
    });
  }
  function sortBy(field: VoiceSessionSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field === "status"
            ? "asc"
            : "desc",
      sortBy: field,
    });
  }
  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="voice-sessions-title"
    >
      <header className="space-y-1">
        <h1
          id="voice-sessions-title"
          className="text-2xl font-semibold tracking-tight"
        >
          Voice sessions
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Inspect the fixed call runtime, provider path, canonical transcript
          state, speech segments, timing, and recordings linked to each
          conversation.
        </p>
      </header>
      <CollectionToolbar
        listLabel="Voice sessions"
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
              aria-label="Search voice sessions"
              maxLength={100}
              placeholder="Search sessions or providers"
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
            listLabel="Voice sessions"
            schema={VOICE_SESSION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Voice sessions"
            options={VOICE_SESSION_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Voice sessions"
            schema={VOICE_SESSION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />
      <VoiceSessionsTable
        agentName={operations.agentName}
        errorMessage={store.collectionErrorMessage}
        hasActiveFilters={hasFilters(query)}
        isLoading={store.isCollectionLoading}
        items={visible}
        onClear={() =>
          setQuery({
            ...query,
            filters: DEFAULT_VOICE_SESSION_QUERY.filters,
            search: "",
          })
        }
        onRetry={() => void store.loadCollection(activeOrganizationId)}
        onView={open}
      />
      <VoiceSessionDetailsDrawer
        organizationId={activeOrganizationId}
        voiceSessionId={voiceSessionId}
        onClose={close}
      />
    </section>
  );
});

function VoiceSessionsTable({
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
  items: readonly VoiceSession[];
  onClear: () => void;
  onRetry: () => void;
  onView: (id: string) => void;
}) {
  if (errorMessage !== null)
    return (
      <Empty
        title="Voice sessions are unavailable"
        description={errorMessage}
        action="Try again"
        onAction={onRetry}
      />
    );
  if (!isLoading && items.length === 0)
    return (
      <Empty
        title={
          hasActiveFilters
            ? "No voice sessions match these filters"
            : "No voice sessions yet"
        }
        description={
          hasActiveFilters
            ? "Change or clear the filters to inspect other sessions."
            : "Voice sessions appear after an end user or telephony call starts a voice Agent."
        }
        action={hasActiveFilters ? "Clear filters" : undefined}
        onAction={onClear}
      />
    );
  return (
    <div className="border">
      <div
        className="divide-y sm:hidden"
        role="list"
        aria-label="Voice sessions"
      >
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => <LoadingCard key={index} />)
          : items.map((session) => (
              <VoiceCard
                key={session.id}
                session={session}
                agentName={agentName(session.agentId)}
                onView={onView}
              />
            ))}
      </div>
      <Table
        className="hidden table-fixed sm:table"
        aria-label="Voice sessions"
      >
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[24%]">Session</TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="hidden w-44 md:table-cell">Agent</TableHead>
            <TableHead className="hidden w-40 lg:table-cell">Runtime</TableHead>
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
            : items.map((session) => (
                <VoiceRow
                  key={session.id}
                  session={session}
                  agentName={agentName(session.agentId)}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading voice sessions…"
          : `${items.length} voice session${items.length === 1 ? "" : "s"} · most recent 100`}
      </div>
    </div>
  );
}

function VoiceRow({
  agentName,
  onView,
  session,
}: {
  agentName: string;
  onView: (id: string) => void;
  session: VoiceSession;
}) {
  const started = formatOperationDate(session.startedAt);
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(session.id)}
        >
          …{session.id.slice(-12)}
        </button>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {session.segmentCount} segments
        </p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{formatOperationEnum(session.status)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal md:table-cell">
        {agentName}
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Badge variant="outline">
          {formatOperationEnum(session.runtimeMode)}
        </Badge>
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        {formatDuration(session.durationMs)}
      </TableCell>
      <TableCell className="whitespace-normal">
        <time dateTime={session.startedAt} title={started.title}>
          {started.label}
        </time>
      </TableCell>
      <TableCell className="text-right">
        <VoiceMenu id={session.id} onView={onView} />
      </TableCell>
    </TableRow>
  );
}
function VoiceCard({
  agentName,
  onView,
  session,
}: {
  agentName: string;
  onView: (id: string) => void;
  session: VoiceSession;
}) {
  const started = formatOperationDate(session.startedAt);
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <button
          className="font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(session.id)}
        >
          Session …{session.id.slice(-12)}
        </button>
        <VoiceMenu id={session.id} onView={onView} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{formatOperationEnum(session.status)}</Badge>
        <Badge variant="outline">
          {formatOperationEnum(session.runtimeMode)}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        {agentName} · {session.segmentCount} segments · {started.label}
      </p>
    </article>
  );
}
function VoiceMenu({
  id,
  onView,
}: {
  id: string;
  onView: (id: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for voice session ${id}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(id)}>
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
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-28" />
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
      <Skeleton className="h-4 w-36" />
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-3 w-44" />
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

export { VoiceSessionsPage };
