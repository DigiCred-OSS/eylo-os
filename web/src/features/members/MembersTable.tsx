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
  formatMemberDate,
  formatMemberStatus,
} from "@/features/members/member-formatters";
import { hasMemberCollectionFilters } from "@/features/members/members.query";
import type {
  Member,
  MemberCollectionQuery,
  MemberSortField,
} from "@/features/members/members.types";

interface MembersTableProps {
  onClearFilters: () => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onSort: (field: MemberSortField) => void;
  onView: (memberId: string) => void;
  query: MemberCollectionQuery;
}

const MembersTable = observer(function MembersTable({
  onClearFilters,
  onPageChange,
  onRetry,
  onSort,
  onView,
  query,
}: MembersTableProps) {
  const { members } = useRootStore();

  if (members.collectionErrorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Members are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {members.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasMemberCollectionFilters(query);
  if (!members.isCollectionLoading && members.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No members match these filters" : "No members found"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to see other members."
            : "Members appear here after they join the organization."}
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
      <div className="divide-y sm:hidden" role="list" aria-label="Members">
        {members.isCollectionLoading
          ? Array.from({ length: 5 }, (_, index) => (
              <MemberLoadingCard key={index} />
            ))
          : members.items.map((member) => (
              <MemberCard key={member.id} member={member} onView={onView} />
            ))}
      </div>

      <Table className="hidden sm:table" aria-label="Members">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              field="name"
              label="Member"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              field="status"
              label="Status"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              className="hidden lg:table-cell"
              field="last_login"
              label="Last login"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              className="hidden xl:table-cell"
              field="created_at"
              label="Joined"
              query={query}
              onSort={onSort}
            />
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {members.isCollectionLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <MemberLoadingRow key={index} />
              ))
            : members.items.map((member) => (
                <MemberRow key={member.id} member={member} onView={onView} />
              ))}
        </TableBody>
      </Table>

      <Pagination
        disabled={members.isCollectionLoading}
        hasMore={members.hasMore}
        itemCount={members.items.length}
        limit={members.limit}
        page={members.page}
        total={members.total}
        onPageChange={onPageChange}
      />
    </div>
  );
});

function MemberRow({
  member,
  onView,
}: {
  member: Member;
  onView: (id: string) => void;
}) {
  return (
    <TableRow>
      <TableCell className="max-w-md whitespace-normal">
        <button
          className="max-w-full text-left font-medium break-words underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(member.id)}
        >
          {member.name}
        </button>
        <p className="mt-0.5 break-all text-xs text-muted-foreground">
          {member.email}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{formatMemberStatus(member.status)}</Badge>
      </TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">
        <DateValue value={member.lastLogin} />
      </TableCell>
      <TableCell className="hidden text-muted-foreground xl:table-cell">
        <DateValue value={member.createdAt} />
      </TableCell>
      <TableCell className="text-right">
        <MemberActions member={member} onView={onView} />
      </TableCell>
    </TableRow>
  );
}

function MemberCard({
  member,
  onView,
}: {
  member: Member;
  onView: (id: string) => void;
}) {
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            className="max-w-full text-left font-medium break-words underline-offset-4 hover:underline"
            type="button"
            onClick={() => onView(member.id)}
          >
            {member.name}
          </button>
          <p className="mt-1 break-all text-sm text-muted-foreground">
            {member.email}
          </p>
        </div>
        <MemberActions member={member} onView={onView} />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{formatMemberStatus(member.status)}</Badge>
        <span>Last login: {formatMemberDate(member.lastLogin).label}</span>
      </div>
    </article>
  );
}

function MemberActions({
  member,
  onView,
}: {
  member: Member;
  onView: (id: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${member.name}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-32">
        <DropdownMenuItem onClick={() => onView(member.id)}>
          <Eye aria-hidden="true" />
          View
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
  field: MemberSortField;
  label: string;
  onSort: (field: MemberSortField) => void;
  query: MemberCollectionQuery;
}) {
  const active = query.sortBy === field;
  const Icon = !active
    ? ArrowUpDown
    : query.direction === "asc"
      ? ArrowUp
      : ArrowDown;
  return (
    <TableHead
      className={className}
      aria-sort={
        active
          ? query.direction === "asc"
            ? "ascending"
            : "descending"
          : "none"
      }
    >
      <Button
        className="-ml-2"
        variant="ghost"
        size="sm"
        onClick={() => onSort(field)}
      >
        {label}
        <Icon className="text-muted-foreground" aria-hidden="true" />
      </Button>
    </TableHead>
  );
}

function DateValue({ value }: { value: string | null | undefined }) {
  const formatted = formatMemberDate(value);
  return formatted.exact === null ? (
    formatted.label
  ) : (
    <time dateTime={formatted.exact} title={formatted.exact}>
      {formatted.label}
    </time>
  );
}

function Pagination({
  disabled,
  hasMore,
  itemCount,
  limit,
  onPageChange,
  page,
  total,
}: {
  disabled: boolean;
  hasMore: boolean;
  itemCount: number;
  limit: number;
  onPageChange: (page: number) => void;
  page: number;
  total: number;
}) {
  const first = itemCount === 0 ? 0 : (page - 1) * limit + 1;
  const last = itemCount === 0 ? 0 : first + itemCount - 1;
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 border-t px-3 py-2">
      <p className="text-xs text-muted-foreground">
        {itemCount === 0
          ? "No members"
          : `${first}–${last} of ${total} members`}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || !hasMore}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function MemberLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-52" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function MemberLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-36" />
      <Skeleton className="h-3 w-52" />
      <Skeleton className="h-5 w-20" />
    </div>
  );
}

export { MembersTable };
