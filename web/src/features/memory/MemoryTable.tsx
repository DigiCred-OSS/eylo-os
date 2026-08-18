import { Ellipsis, Eye } from "lucide-react";
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
  formatMemoryDate,
  formatMemoryLevel,
  formatMemoryStatus,
} from "@/features/memory/memory-formatters";
import { MemoryIntegrityBadge } from "@/features/memory/MemoryIntegrityBadge";
import { hasMemoryCollectionFilters } from "@/features/memory/memory.query";
import type {
  Memory,
  MemoryCollectionQuery,
} from "@/features/memory/memory.types";

interface MemoryTableProps {
  onClearFilters: () => void;
  onLoadMore: () => void;
  onRetry: () => void;
  onView: (memoryId: string) => void;
  query: MemoryCollectionQuery;
}

const MemoryTable = observer(function MemoryTable({
  onClearFilters,
  onLoadMore,
  onRetry,
  onView,
  query,
}: MemoryTableProps) {
  const { memory } = useRootStore();

  if (memory.collectionErrorMessage !== null && memory.items.length === 0) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Memories are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {memory.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasMemoryCollectionFilters(query);
  if (!memory.isCollectionLoading && memory.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No memories match these filters" : "No memories yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to inspect other memories."
            : "Memories appear after an Agent remembers or learns from a conversation."}
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
      <div className="divide-y sm:hidden" role="list" aria-label="Memories">
        {memory.isCollectionLoading && memory.items.length === 0
          ? Array.from({ length: 5 }, (_, index) => (
              <MemoryLoadingCard key={index} />
            ))
          : memory.items.map((item) => (
              <MemoryCard key={item.id} memory={item} onView={onView} />
            ))}
      </div>

      <Table className="hidden table-fixed sm:table" aria-label="Memories">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[30%]">Memory</TableHead>
            <TableHead className="w-20">Level</TableHead>
            <TableHead className="hidden w-[14%] md:table-cell">
              Subject
            </TableHead>
            <TableHead className="w-24">Status</TableHead>
            <TableHead className="w-24">Integrity</TableHead>
            <TableHead className="hidden w-20 lg:table-cell">
              Recalled
            </TableHead>
            <TableHead className="hidden w-32 xl:table-cell">Updated</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {memory.isCollectionLoading && memory.items.length === 0
            ? Array.from({ length: 6 }, (_, index) => (
                <MemoryLoadingRow key={index} />
              ))
            : memory.items.map((item) => (
                <MemoryRow key={item.id} memory={item} onView={onView} />
              ))}
        </TableBody>
      </Table>

      {!memory.isCollectionLoading ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-3 py-3">
          <p className="text-xs text-muted-foreground">
            Showing {memory.items.length} of {memory.total} memories
          </p>
          {memory.canLoadMore ? (
            <Button
              size="sm"
              variant="outline"
              disabled={memory.isLoadingMore}
              onClick={onLoadMore}
            >
              {memory.isLoadingMore ? "Loading…" : "Load more"}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
});

function MemoryRow({
  memory,
  onView,
}: {
  memory: Memory;
  onView: (memoryId: string) => void;
}) {
  const updated = formatMemoryDate(memory.updated_at);
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <button
          className="block w-full break-words text-left font-medium whitespace-pre-wrap underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(memory.id)}
        >
          {memory.content}
        </button>
      </TableCell>
      <TableCell className="whitespace-normal">
        <Badge variant="outline">{formatMemoryLevel(memory.level)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal md:table-cell">
        <span className="break-words">{memory.subject_label}</span>
      </TableCell>
      <TableCell>
        <MemoryStatusBadge memory={memory} />
      </TableCell>
      <TableCell>
        <MemoryIntegrityBadge integrity={memory.integrity} />
      </TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">
        {memory.recall_count === 0 ? "Never" : `${memory.recall_count}×`}
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground xl:table-cell">
        <DateValue value={updated} />
      </TableCell>
      <TableCell className="text-right">
        <MemoryActions memory={memory} onView={onView} />
      </TableCell>
    </TableRow>
  );
}

function MemoryCard({
  memory,
  onView,
}: {
  memory: Memory;
  onView: (memoryId: string) => void;
}) {
  const updated = formatMemoryDate(memory.updated_at);
  return (
    <article
      className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 p-4"
      role="listitem"
    >
      <button
        className="min-w-0 text-left focus-visible:rounded-sm focus-visible:outline-2"
        type="button"
        onClick={() => onView(memory.id)}
      >
        <span className="block break-words text-sm font-medium whitespace-pre-wrap">
          {memory.content}
        </span>
        <span className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Badge variant="outline">{formatMemoryLevel(memory.level)}</Badge>
          <span className="break-words">{memory.subject_label}</span>
        </span>
        <span className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span>Status</span>
            <MemoryStatusBadge memory={memory} />
          </span>
          <span className="inline-flex items-center gap-1">
            <span>Integrity</span>
            <MemoryIntegrityBadge integrity={memory.integrity} />
          </span>
          <span>
            {memory.recall_count === 0
              ? "Never recalled"
              : `Recalled ${memory.recall_count}×`}
          </span>
          <span>Updated {updated.label}</span>
        </span>
      </button>
      <MemoryActions memory={memory} onView={onView} />
    </article>
  );
}

function MemoryStatusBadge({ memory }: { memory: Memory }) {
  return (
    <Badge variant={memory.status === "expired" ? "secondary" : "outline"}>
      {formatMemoryStatus(memory.status)}
    </Badge>
  );
}

function MemoryActions({
  memory,
  onView,
}: {
  memory: Memory;
  onView: (memoryId: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for memory ${memory.id}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        <DropdownMenuItem onClick={() => onView(memory.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function DateValue({
  value,
}: {
  value: { exact: string | null; label: string };
}) {
  return value.exact === null ? (
    value.label
  ) : (
    <time dateTime={value.exact} title={`${value.exact} (UTC)`}>
      {value.label}
    </time>
  );
}

function MemoryLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-full" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-16" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-10" />
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

function MemoryLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-3 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

export { MemoryTable };
