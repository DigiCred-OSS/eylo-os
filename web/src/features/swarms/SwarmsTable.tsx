import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Ellipsis,
  Eye,
  Pencil,
  Trash2,
} from "lucide-react";
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
import { formatSwarmDate } from "@/features/swarms/swarm-formatters";
import { SwarmLifecycleBadge } from "@/features/swarms/SwarmLifecycleBadge";
import { hasSwarmCollectionFilters } from "@/features/swarms/swarms.query";
import type {
  Swarm,
  SwarmCollectionQuery,
  SwarmSortField,
} from "@/features/swarms/swarms.types";

interface SwarmsTableProps {
  onClearFilters: () => void;
  onDelete: (swarm: Swarm) => void;
  onEdit: (swarmId: string) => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onSort: (field: SwarmSortField) => void;
  onView: (swarmId: string) => void;
  query: SwarmCollectionQuery;
}

const SwarmsTable = observer(function SwarmsTable({
  onClearFilters,
  onDelete,
  onEdit,
  onPageChange,
  onRetry,
  onSort,
  onView,
  query,
}: SwarmsTableProps) {
  const { swarms } = useRootStore();
  if (swarms.collectionErrorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Swarms are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {swarms.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasSwarmCollectionFilters(query);
  if (!swarms.isCollectionLoading && swarms.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No Swarms match these filters" : "No Swarms yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to see other Swarms."
            : "Create a Swarm to define a coordinated Agent topology."}
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
      <Table aria-label="Swarms">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              field="name"
              label="Name"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden min-w-72 lg:table-cell">
              Description
            </TableHead>
            <SortableHead
              field="lifecycle"
              label="Lifecycle"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden md:table-cell">Draft</TableHead>
            <SortableHead
              className="hidden sm:table-cell"
              field="updated_at"
              label="Updated"
              query={query}
              onSort={onSort}
            />
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {swarms.isCollectionLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <SwarmLoadingRow key={index} />
              ))
            : swarms.items.map((swarm) => (
                <SwarmRow
                  key={swarm.id}
                  swarm={swarm}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="flex min-h-14 items-center justify-between gap-4 border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          {paginationLabel(
            swarms.page,
            swarms.limit,
            swarms.items.length,
            swarms.total,
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={swarms.isCollectionLoading || swarms.page <= 1}
            onClick={() => onPageChange(swarms.page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={swarms.isCollectionLoading || !swarms.hasMore}
            onClick={() => onPageChange(swarms.page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
});

function SwarmRow({
  onDelete,
  onEdit,
  onView,
  swarm,
}: {
  onDelete: (swarm: Swarm) => void;
  onEdit: (swarmId: string) => void;
  onView: (swarmId: string) => void;
  swarm: Swarm;
}) {
  return (
    <TableRow>
      <TableCell className="max-w-64 whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(swarm.id)}
        >
          {swarm.name}
        </button>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {swarm.slug}
        </p>
      </TableCell>
      <TableCell className="hidden max-w-96 whitespace-normal text-muted-foreground lg:table-cell">
        <p className="line-clamp-2 leading-5">
          {swarm.description?.trim() || "No description"}
        </p>
      </TableCell>
      <TableCell>
        <SwarmLifecycleBadge lifecycle={swarm.lifecycle} />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">
          {swarm.draftDirty ? "Changes pending" : "Current"}
        </Badge>
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">
        <DateValue value={swarm.updatedAt} />
      </TableCell>
      <TableCell className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Actions for ${swarm.name}`}
              />
            }
          >
            <Ellipsis aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36">
            <DropdownMenuItem onClick={() => onView(swarm.id)}>
              <Eye aria-hidden="true" />
              View
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onEdit(swarm.id)}>
              <Pencil aria-hidden="true" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive"
              disabled={swarm.publishedRevision != null}
              title={
                swarm.publishedRevision == null
                  ? "Delete draft Swarm"
                  : "Published Swarms are retained for exact run references"
              }
              onClick={() => onDelete(swarm)}
            >
              <Trash2 aria-hidden="true" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
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
  field: SwarmSortField;
  label: string;
  onSort: (field: SwarmSortField) => void;
  query: SwarmCollectionQuery;
}) {
  const isActive = query.sortBy === field;
  const Icon = !isActive
    ? ArrowUpDown
    : query.direction === "asc"
      ? ArrowUp
      : ArrowDown;
  return (
    <TableHead
      className={className}
      aria-sort={
        isActive
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
  const formatted = formatSwarmDate(value);
  return formatted.exact === null ? (
    formatted.label
  ) : (
    <time dateTime={formatted.exact} title={`${formatted.exact} (UTC)`}>
      {formatted.label}
    </time>
  );
}

function paginationLabel(
  page: number,
  limit: number,
  count: number,
  total: number,
): string {
  if (count === 0) return "No Swarms";
  const first = (page - 1) * limit + 1;
  return `${first}–${first + count - 1} of ${total} Swarms`;
}

function SwarmLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-full max-w-72" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-5 w-24" />
      </TableCell>
      <TableCell className="hidden sm:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

export { SwarmsTable };
