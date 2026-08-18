import { ArrowDown, ArrowUp, ArrowUpDown, Ellipsis, Eye } from "lucide-react";
import { observer } from "mobx-react-lite";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  formatSessionContact,
  formatSessionDate,
  formatSessionEnum,
} from "@/features/sessions/session-formatters";
import { hasSessionCollectionFilters } from "@/features/sessions/sessions.query";
import type {
  SessionCollectionQuery,
  UserSession,
  UserSessionSortField,
} from "@/features/sessions/sessions.types";

interface SessionsTableProps {
  onClearFilters: () => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onSort: (field: UserSessionSortField) => void;
  onView: (userSessionId: string) => void;
  query: SessionCollectionQuery;
}

const SessionsTable = observer(function SessionsTable({
  onClearFilters,
  onPageChange,
  onRetry,
  onSort,
  onView,
  query,
}: SessionsTableProps) {
  const { sessions } = useRootStore();

  if (sessions.collectionErrorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Sessions are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {sessions.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasSessionCollectionFilters(query);
  if (!sessions.isCollectionLoading && sessions.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No sessions match these filters" : "No sessions yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to inspect other sessions."
            : "Sessions appear when an end user opens the widget or starts a call."}
        </p>
        {hasFilters ? (
          <Button className="mt-4" variant="outline" onClick={onClearFilters}>
            Clear filters
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="border">
      <div className="divide-y sm:hidden" role="list" aria-label="Sessions">
        {sessions.isCollectionLoading
          ? Array.from({ length: 5 }, (_, index) => (
              <SessionLoadingCard key={index} />
            ))
          : sessions.items.map((userSession) => (
              <SessionCard
                key={userSession.id}
                userSession={userSession}
                onView={onView}
              />
            ))}
      </div>

      <Table className="hidden table-fixed sm:table" aria-label="Sessions">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              className="w-[30%]"
              field="contact"
              label="Contact"
              query={query}
              onSort={onSort}
            />
            <TableHead className="w-32">State</TableHead>
            <TableHead className="w-28">Entry</TableHead>
            <SortableHead
              className="w-44"
              field="started_at"
              label="Started"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              className="hidden w-44 lg:table-cell"
              field="last_activity_at"
              label="Last activity"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden w-28 md:table-cell">Events</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sessions.isCollectionLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <SessionLoadingRow key={index} />
              ))
            : sessions.items.map((userSession) => (
                <SessionRow
                  key={userSession.id}
                  userSession={userSession}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>

      <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          {paginationLabel(
            sessions.page,
            sessions.limit,
            sessions.items.length,
            sessions.total,
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={sessions.isCollectionLoading || sessions.page <= 1}
            onClick={() => onPageChange(sessions.page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={sessions.isCollectionLoading || !sessions.hasMore}
            onClick={() => onPageChange(sessions.page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
});

function SessionRow({
  onView,
  userSession,
}: {
  onView: (userSessionId: string) => void;
  userSession: UserSession;
}) {
  const started = formatSessionDate(userSession.startedAt);
  const activity = formatSessionDate(userSession.lastActivityAt);
  return (
    <TableRow>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          className="block max-w-full break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(userSession.id)}
        >
          {formatSessionContact(userSession.contact)}
        </button>
        <p className="mt-0.5 break-all text-xs text-muted-foreground">
          …{userSession.id.slice(-12)}
        </p>
      </TableCell>
      <TableCell>
        <SessionStateBadge state={userSession.state} />
      </TableCell>
      <TableCell>
        <Badge variant="outline">
          {formatSessionEnum(userSession.entryChannel)}
        </Badge>
      </TableCell>
      <TableCell className="whitespace-normal">
        <time dateTime={userSession.startedAt} title={started.title}>
          {started.label}
        </time>
      </TableCell>
      <TableCell className="hidden whitespace-normal lg:table-cell">
        <time dateTime={userSession.lastActivityAt} title={activity.title}>
          {activity.label}
        </time>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        {userSession.counts.timelineEvents}
      </TableCell>
      <TableCell className="text-right">
        <SessionActions userSessionId={userSession.id} onView={onView} />
      </TableCell>
    </TableRow>
  );
}

function SessionCard({
  onView,
  userSession,
}: {
  onView: (userSessionId: string) => void;
  userSession: UserSession;
}) {
  const started = formatSessionDate(userSession.startedAt);
  return (
    <article className="min-w-0 space-y-3 p-4" role="listitem">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            className="break-words text-left font-medium underline-offset-4 hover:underline"
            type="button"
            onClick={() => onView(userSession.id)}
          >
            {formatSessionContact(userSession.contact)}
          </button>
          <p className="mt-1 break-all text-xs text-muted-foreground">
            {userSession.id}
          </p>
        </div>
        <SessionActions userSessionId={userSession.id} onView={onView} />
      </div>
      <div className="flex flex-wrap gap-2">
        <SessionStateBadge state={userSession.state} />
        <Badge variant="outline">
          {formatSessionEnum(userSession.entryChannel)}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        Started <time dateTime={userSession.startedAt}>{started.label}</time> ·{" "}
        {userSession.counts.timelineEvents} events
      </p>
    </article>
  );
}

function SessionStateBadge({ state }: { state: UserSession["state"] }) {
  return (
    <Badge variant={state === "failed" ? "destructive" : "secondary"}>
      {formatSessionEnum(state)}
    </Badge>
  );
}

function SessionActions({
  onView,
  userSessionId,
}: {
  onView: (userSessionId: string) => void;
  userSessionId: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon" aria-label="Session actions" />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(userSessionId)}>
          <Eye aria-hidden="true" />
          View timeline
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
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
  field: UserSessionSortField;
  label: string;
  onSort: (field: UserSessionSortField) => void;
  query: SessionCollectionQuery;
}) {
  const active = query.sortBy === field;
  const Icon = !active
    ? ArrowUpDown
    : query.direction === "asc"
      ? ArrowUp
      : ArrowDown;
  return (
    <TableHead className={className}>
      <Button
        className="-ml-3"
        size="sm"
        variant="ghost"
        onClick={() => onSort(field)}
      >
        {label}
        <Icon aria-hidden="true" />
      </Button>
    </TableHead>
  );
}

function SessionLoadingRow() {
  return (
    <TableRow>
      {Array.from({ length: 7 }, (_, index) => (
        <TableCell key={index}>
          <Skeleton className="h-5 w-full" />
        </TableCell>
      ))}
    </TableRow>
  );
}

function SessionLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-5 w-3/5" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-5 w-2/5" />
    </div>
  );
}

function paginationLabel(
  page: number,
  limit: number,
  count: number,
  total: number,
): string {
  if (count === 0) {
    return "No sessions";
  }
  const start = (page - 1) * limit + 1;
  return `Showing ${start}–${start + count - 1} of ${total} sessions`;
}

export { SessionsTable };
