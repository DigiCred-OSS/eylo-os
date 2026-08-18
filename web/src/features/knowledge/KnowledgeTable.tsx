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
import {
  formatKnowledgeDate,
  formatKnowledgeScope,
  formatKnowledgeVendor,
} from "@/features/knowledge/knowledge-formatters";
import { hasKnowledgeCollectionFilters } from "@/features/knowledge/knowledge.query";
import type {
  Knowledgebase,
  KnowledgeCollectionQuery,
  KnowledgeSortField,
} from "@/features/knowledge/knowledge.types";

interface KnowledgeTableProps {
  items: readonly Knowledgebase[];
  onClearFilters: () => void;
  onDelete: (knowledgebase: Knowledgebase) => void;
  onEdit: (knowledgebaseId: string) => void;
  onRetry: () => void;
  onSort: (field: KnowledgeSortField) => void;
  onView: (knowledgebaseId: string) => void;
  query: KnowledgeCollectionQuery;
}

const KnowledgeTable = observer(function KnowledgeTable({
  items,
  onClearFilters,
  onDelete,
  onEdit,
  onRetry,
  onSort,
  onView,
  query,
}: KnowledgeTableProps) {
  const { knowledge } = useRootStore();

  if (
    knowledge.collectionErrorMessage !== null &&
    knowledge.items.length === 0
  ) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Knowledgebases are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {knowledge.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasKnowledgeCollectionFilters(query);
  if (!knowledge.isCollectionLoading && items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters
            ? "No knowledgebases match these filters"
            : "No knowledgebases yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to see other knowledgebases."
            : "Create a knowledgebase, then add content for an Agent to retrieve."}
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
      <div
        className="divide-y sm:hidden"
        role="list"
        aria-label="Knowledgebases"
      >
        {knowledge.isCollectionLoading && knowledge.items.length === 0
          ? Array.from({ length: 5 }, (_, index) => (
              <KnowledgeLoadingCard key={index} />
            ))
          : items.map((knowledgebase) => (
              <KnowledgeCard
                key={knowledgebase.id}
                knowledgebase={knowledgebase}
                onDelete={onDelete}
                onEdit={onEdit}
                onView={onView}
              />
            ))}
      </div>

      <Table className="hidden sm:table" aria-label="Knowledgebases">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              field="name"
              label="Name"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              field="vendor"
              label="Search method"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              className="hidden md:table-cell"
              field="scope"
              label="Scope"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden lg:table-cell">Agent writes</TableHead>
            <TableHead className="hidden xl:table-cell">Model</TableHead>
            <SortableHead
              className="hidden lg:table-cell"
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
          {knowledge.isCollectionLoading && knowledge.items.length === 0
            ? Array.from({ length: 6 }, (_, index) => (
                <KnowledgeLoadingRow key={index} />
              ))
            : items.map((knowledgebase) => (
                <KnowledgeRow
                  key={knowledgebase.id}
                  knowledgebase={knowledgebase}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>

      {!knowledge.isCollectionLoading ? (
        <p className="border-t px-3 py-3 text-xs text-muted-foreground">
          {items.length === 1
            ? "1 knowledgebase"
            : `${items.length} knowledgebases`}
        </p>
      ) : null}
    </div>
  );
});

function KnowledgeRow({
  knowledgebase,
  onDelete,
  onEdit,
  onView,
}: {
  knowledgebase: Knowledgebase;
  onDelete: (knowledgebase: Knowledgebase) => void;
  onEdit: (knowledgebaseId: string) => void;
  onView: (knowledgebaseId: string) => void;
}) {
  const updatedAt = formatKnowledgeDate(knowledgebase.updated_at);
  return (
    <TableRow>
      <TableCell className="max-w-64 whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(knowledgebase.id)}
        >
          {knowledgebase.name}
        </button>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {knowledgebase.slug}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">
          {formatKnowledgeVendor(knowledgebase.vendor)}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">
          {formatKnowledgeScope(knowledgebase.scope)}
        </Badge>
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Badge variant="outline">
          {knowledgebase.writable ? "By explicit grant" : "Read-only"}
        </Badge>
      </TableCell>
      <TableCell className="hidden max-w-64 truncate text-muted-foreground xl:table-cell">
        {knowledgebase.embedding_model ?? "Not applicable"}
      </TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">
        {updatedAt.exact === null ? (
          updatedAt.label
        ) : (
          <time dateTime={updatedAt.exact} title={`${updatedAt.exact} (UTC)`}>
            {updatedAt.label}
          </time>
        )}
      </TableCell>
      <TableCell className="text-right">
        <KnowledgeActions
          knowledgebase={knowledgebase}
          onDelete={onDelete}
          onEdit={onEdit}
          onView={onView}
        />
      </TableCell>
    </TableRow>
  );
}

function KnowledgeCard({
  knowledgebase,
  onDelete,
  onEdit,
  onView,
}: {
  knowledgebase: Knowledgebase;
  onDelete: (knowledgebase: Knowledgebase) => void;
  onEdit: (knowledgebaseId: string) => void;
  onView: (knowledgebaseId: string) => void;
}) {
  const updatedAt = formatKnowledgeDate(knowledgebase.updated_at);
  return (
    <article
      className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 p-4"
      role="listitem"
    >
      <button
        className="min-w-0 text-left focus-visible:rounded-sm focus-visible:outline-2"
        type="button"
        onClick={() => onView(knowledgebase.id)}
      >
        <span className="block truncate text-sm font-medium">
          {knowledgebase.name}
        </span>
        <span className="mt-2 flex flex-wrap gap-1.5">
          <Badge variant="outline">
            {formatKnowledgeVendor(knowledgebase.vendor)}
          </Badge>
          <Badge variant="outline">
            {formatKnowledgeScope(knowledgebase.scope)}
          </Badge>
        </span>
        <span className="mt-2 block text-xs text-muted-foreground">
          Updated {updatedAt.label}
        </span>
      </button>
      <KnowledgeActions
        knowledgebase={knowledgebase}
        onDelete={onDelete}
        onEdit={onEdit}
        onView={onView}
      />
    </article>
  );
}

function KnowledgeActions({
  knowledgebase,
  onDelete,
  onEdit,
  onView,
}: {
  knowledgebase: Knowledgebase;
  onDelete: (knowledgebase: Knowledgebase) => void;
  onEdit: (knowledgebaseId: string) => void;
  onView: (knowledgebaseId: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${knowledgebase.name}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <DropdownMenuItem onClick={() => onView(knowledgebase.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onEdit(knowledgebase.id)}>
          <Pencil aria-hidden="true" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem
          className="text-destructive"
          onClick={() => onDelete(knowledgebase)}
        >
          <Trash2 aria-hidden="true" />
          Delete
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
  field: KnowledgeSortField;
  label: string;
  onSort: (field: KnowledgeSortField) => void;
  query: KnowledgeCollectionQuery;
}) {
  const isActive = query.sortBy === field;
  const ariaSort = isActive
    ? query.direction === "asc"
      ? "ascending"
      : "descending"
    : "none";
  const Icon = !isActive
    ? ArrowUpDown
    : query.direction === "asc"
      ? ArrowUp
      : ArrowDown;

  return (
    <TableHead className={className} aria-sort={ariaSort}>
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

function KnowledgeLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-24" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-4 w-36" />
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

function KnowledgeLoadingCard() {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-3 p-4">
      <div>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-48" />
        <Skeleton className="mt-3 h-3 w-28" />
      </div>
      <Skeleton className="size-8" />
    </div>
  );
}

export { KnowledgeTable };
